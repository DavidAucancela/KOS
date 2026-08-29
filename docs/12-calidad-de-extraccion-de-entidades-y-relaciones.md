# 12 — Calidad de extracción: resolución de entidades y relaciones cross-documento

**Estado:** 🟡 Borrador · **Última actualización:** 2026-08-27 · **Habilita:** mejora sobre la
ingesta ya habilitada por [05 — Ingesta y actualización](05-ingesta-y-actualizacion.md) (Fase 1)

> **Addendum 2026-08-27 (§10):** el rediseño §3–§6 se construyó y se corrió el backfill, y el grafo
> pasó de 312 a 370 relaciones — 84% de los nodos sigue aislado. La causa no era la que §1 asumía
> como corregible: el modelo local (`llama3.2:latest`, 3B) no sostiene el contrato de salida JSON
> de `s8_relations.py`, así que la extracción de relaciones rinde casi cero y no hay hardware para
> un modelo más grande. §10 cambia el enfoque: la **estructura del propio vault** (`[[wikilinks]]`,
> tags, frontmatter) y la **co-ocurrencia de entidades** pasan a ser la fuente primaria de
> aristas; el LLM queda como refuerzo opcional. Las secciones §1–§9 se conservan como registro del
> diagnóstico y del intento previo.
>
> **Construido el 2026-08-27** (§10.4 y §10.5, sin sprint numerado — trabajo de deuda):
> `pipeline/structural.py` (frontmatter tipado, puro), `_sync_structural_edges` en
> `tasks/graph_sync.py` (nodo `Document` por nota + wikilinks + nota↔entidad + tags compartidos),
> `sync_cooccurrence_relations` + la task encadenada `kos.discover_cooccurrence_relations`
> (`tasks/cooccurrence_relations.py`), y la pasada completa en `scripts/backfill_graph_extraction.py`.
> `merge_node` acepta ahora `extracted_by` para trazar procedencia (§10.7). **Diferido a propósito:**
> §10.6 (refuerzo LLM binario) — el grafo queda conectado sin él; se evalúa con datos una vez
> corrido el backfill. **Falta ejecutar el backfill** contra el vault real para verificar §10.7.

## 1. Problema y diagnóstico

Verificando la UI del grafo (`apps/web`, pantalla "Grafo de conocimiento") se midió el estado real
del grafo en Neo4j:

| Métrica | Valor |
|---|---|
| Nodos totales | 2.284 |
| Relaciones totales | 312 |
| Nodos sin ninguna relación | 1.952 (**85%**) |
| Tipo de nodo dominante | `Concept`, 947 (41%) |

Un grafo con menos de 1 relación cada 7 nodos no sirve como grafo — la mayoría de las entidades
extraídas quedan como puntos sueltos, sin conectar la misma idea entre notas distintas. Revisando
el pipeline de ingesta (`apps/workers/src/kos_workers/pipeline/`, doc 05 §3) se encontraron tres
causas concretas, no un bug puntual:

### 1.1 Extracción de relaciones ciega entre documentos

`s8_relations.py::build_relations_prompt` arma el prompt solo con `entity_names` provenientes de
`doc.entities` — las entidades detectadas *en el mismo documento* por la etapa 7 que corrió justo
antes, dentro del mismo `_sync_graph` (`apps/workers/src/kos_workers/tasks/graph_sync.py`). Si
"Kubernetes" aparece en 30 notas, cada extracción es ciega a las otras 29: no existe ningún paso
que compare entidades de documentos distintos y proponga una relación entre ellas. Esta es la causa
principal de la dispersión — con 2.284 nodos repartidos en ~154 documentos, la mayoría de las
relaciones reales de un vault personal (la misma tecnología usada en proyectos distintos, el mismo
concepto retomado en notas separadas) son estructuralmente invisibles para el pipeline actual.

### 1.2 Resolución de entidades débil y cara

`canonicalize()` (`packages/core/src/kos_core/ontology/__init__.py:15`) es normalización de
superficie pura — minúsculas, NFKD sin acentos, sin puntuación/espacios — sin tabla de sinónimos ni
alias: `"Kubernetes"` y `"k8s"` canonicalizan a strings distintos y nunca matchean por igualdad
exacta (doc 05 §4 paso 2).

El fallback por embeddings sí existe (`graph_sync.py::_resolve_entity`, doc 05 §4 paso 3), pero:
- Trae **todos** los nodos existentes de ese tipo (`fetch_nodes_by_type`) y calcula similitud coseno
  en memoria contra cada uno (`_cosine_similarity`), re-embedeando el nombre candidato en cada
  llamada — sin índice, sin embeddings de nodo persistidos en ningún lado.
- El umbral (`SIMILARITY_THRESHOLD = 0.9`) es alto y fijo — filtra paráfrasis razonables antes de
  siquiera llegar al veredicto LLM (`_default_merge_verdict`).

`merge_node` (`packages/core/src/kos_core/storage/neo4j.py`) sí upsertea correctamente por
`canonical_name` una vez que dos candidatos llegan a ese punto — el problema es todo lo que pasa
*antes*, no el merge en sí.

### 1.3 Truncamiento a documento completo en vez de chunks

Tanto `s7_entities.py` como `s8_relations.py` truncan a `max_chars * 4 = 8000` caracteres de
`doc.body` reconstruido, en vez de iterar `doc.chunks` — que ya existen (`s3_chunking.py`), ya
están embebidos en pgvector (`s4_embeddings.py`) con offsets precisos. Consecuencia directa:
documentos largos pierden contenido para extracción sin que nada lo señale, y
`EntityCandidate.chunk_ids`/`RelationCandidate.chunk_ids` (`packages/core/src/kos_core/schemas/entities.py`)
quedan siempre vacíos — campos del esquema reservados para esto que el pipeline nunca pobló.

## 2. Principio de diseño

No se propone un mecanismo nuevo desde cero: el Recomendador (doc 11 §4/§5, Sprint 24) ya resuelve
un problema estructuralmente idéntico — comparar contenido entre documentos distintos, de forma
barata, sin confiar la decisión final a un LLM solo — con el patrón **"candidatos determinísticos
vía pgvector + veredicto LLM conservador con fail-safe"**:

- `search_storage.similarity_band_chunks()` (`packages/core/src/kos_core/storage/search.py:365`):
  búsqueda pgvector real (`<=>`, indexada), banda de similitud configurable, ya excluye el propio
  documento (`exclude_doc_id`).
- `_default_contradiction_verdict()` / `_default_merge_verdict()`: mismo patrón de veredicto LLM
  con fail-safe a "no" en ambigüedad ("reglas y consultas de grafo determinísticas, no un loop de
  planificación LLM", doc 11 §5) — ya probado en Sprint 6 (merge de entidades) y Sprint 24
  (contradicciones).
- Entrega: cadena de tasks de Celery, no pub/sub (`kos.graph_sync` → `kos.recommend_from_graph_update`,
  doc 11 §3) — un subscriber de Redis pub/sub perdería eventos mientras no corre; la cadena de
  tasks no.

Este documento extiende ese mismo patrón a una tercera aplicación: relaciones cross-documento y
resolución de entidades indexada.

## 3. Resolución de entidades (rediseño)

- **Nueva tabla pgvector** (Postgres, vía Alembic — doc 09 `make migrate`): embeddings de nodo
  persistidos, `node_id` (referencia al `id` de Neo4j), `canonical_name`, `node_type`,
  `embedding vector(1024)` — mismo modelo bge-m3 vía `OllamaEmbeddingClient` que ya usan los
  chunks, no un modelo nuevo.
- Al resolver un candidato: paso 1 sigue siendo `canonicalize()` exacto (barato, cubre el caso
  común de repetición literal); si no matchea, se hace una búsqueda ANN indexada contra la tabla
  nueva en vez del loop en memoria actual — mismo principio de índice que ya usa
  `similarity_band_chunks` para chunks.
- Banda de similitud más amplia que el 0.9 fijo actual (a calibrar, ej. 0.75–0.95) antes de pedir
  veredicto LLM — reutiliza `_default_merge_verdict` tal cual, solo cambia cómo se generan los
  candidatos a evaluar.
- La tabla se actualiza en el mismo commit que `merge_node` escribe/actualiza un nodo en Neo4j —
  mismo problema de consistencia eventual entre Postgres/Neo4j que doc 02 §5 ya reconoce y acepta
  para chunks/relaciones.

## 4. Extracción de relaciones cross-documento (rediseño)

Nueva etapa, reactiva tras `kos.graph_sync` (mismo punto de encadenamiento que hoy dispara
`kos.recommend_from_graph_update`, doc 11 §3):

1. Para los chunks del documento recién ingerido, buscar chunks de *otros* documentos en banda de
   similitud vía `similarity_band_chunks()` — floor/ceiling a definir en implementación (partir de
   los mismos `CONTRADICTION_SIMILARITY_FLOOR/CEILING` de `recommend.py` como punto de referencia,
   o una banda propia si la calibración lo pide).
2. Para cada par de chunks en banda, juntar las entidades ya resueltas de ambos documentos — esto
   depende de que `chunk_ids` esté poblado (§5) para saber qué entidades corresponden a qué chunk.
3. Prompt LLM restringido a "solo relaciones entre entidades ya detectadas" (mismo principio que
   `s8_relations.py` aplica intra-documento hoy, doc 05 §3 etapa 8) pero extendido a la unión de
   ambas bolsas de entidades — nunca inventa entidades nuevas, solo relaciones entre las que ya
   existen en el grafo.
4. El resultado se escribe con el mismo camino que las relaciones intra-documento (`merge_relation`,
   `sources[]` acumulando ambos documentos como evidencia).

## 5. Extracción por chunk en vez de truncar el documento

- `s7_entities.py`/`s8_relations.py` iteran `doc.chunks` en vez de truncar `doc.body` a 8000
  caracteres — cobertura completa de documentos largos.
- Se pueblan por fin `EntityCandidate.chunk_ids`/`RelationCandidate.chunk_ids` — prerequisito
  técnico directo de §4 (sin saber qué chunk originó cada entidad, no se puede cruzar documentos a
  nivel de chunk).
- **Costo/riesgo**: más llamadas LLM por documento (una por chunk en vez de una por documento
  completo) — ver §7, impacto en la garantía de latencia de doc 05 §6.

## 6. Backfill del grafo existente

`kos reindex` (doc 05 §5) ya es idempotente y basado en hash de contenido, reconstruyendo desde
MinIO + fuentes. Como `merge_node` upsertea por `canonical_name`, reprocesar los 2.284 nodos
existentes con el pipeline rediseñado no debería duplicar nodos — solo mejorar su resolución y
sumar las relaciones cross-documento que hoy no existen.

Se recomienda correr el reindex primero sobre un subconjunto pequeño de documentos (ej. los que ya
se sabe que comparten temas, para verificar visualmente que aparecen relaciones nuevas) antes del
reindex completo — dado el costo de re-embedear y re-promptear ~154 documentos contra un LLM local.

## 7. Riesgos y no-objetivos

| Riesgo | Tratamiento |
|---|---|
| `llama3.2` (modelo local chico) es conservador en veredictos LLM — doc 11 §4 ya documentó que confirmó pocas contradicciones incluso obvias | Riesgo conocido, documentado, sin mitigación de diseño en este doc — mismo criterio que doc 11 §4 le dio a las contradicciones. Ajuste de prompt o modelo distinto queda como deuda futura, no bloquea este diseño. |
| Extracción por chunk multiplica llamadas LLM por documento | Latencia — doc 05 §6 exige <5min para Fase 3; a validar en implementación si el chunking por documento largo lo pone en riesgo. |
| Nueva tabla pgvector de embeddings de nodo | Requiere migración Alembic (doc 09 `make migrate`) — no es una decisión de storage nueva (ADR-0002 ya eligió pgvector), así que no hace falta ADR nuevo, solo la migración. |
| Consistencia eventual Postgres (embeddings de nodo) ↔ Neo4j (nodo real) | Mismo modelo ya aceptado en doc 02 §5 para chunks/relaciones — no se resuelve con transacciones cross-store. |

**Fuera de alcance de este documento:**
- Nodo `Claim` (diferido a v1.1/Fase 3, doc 02 §6) — este diseño no lo necesita ni lo adelanta.
- Cambios a la ontología cerrada (tipos de nodo/relación, doc 02 §4 regla 1) — ningún tipo nuevo se
  propone acá.
- Rediseñar el mecanismo de veredicto LLM para evitar el sesgo conservador del modelo — ver tabla
  de riesgos arriba.

## 8. Métricas / criterio de éxito

- **% de nodos con grado ≥ 1** (hoy ~15%, 332/2.284) como métrica principal — medida antes y
  después del backfill (§6).
- Relaciones totales — no se espera ni se busca "cerrar" el grafo a un solo componente conectado;
  un vault personal real va a seguir teniendo entidades genuinamente aisladas (una nota suelta sin
  ninguna conexión temática con el resto). El objetivo es que la dispersión baje de "85% aislado"
  a algo consistente con la densidad temática real del vault, no a cero.

## 9. Evolución por fases

| Fase | Qué cubre |
|---|---|
| Esta iteración (mejora sobre Fase 1, doc 05) | Resolución de entidades indexada (§3), relaciones cross-documento (§4), extracción por chunk (§5), backfill del grafo actual (§6) |
| Fase 3 (v1.1, doc 02 §6) | Nodo `Claim` — asserciones atómicas con vigencia temporal; sigue diferido, no lo toca este documento |
| Fase 6 (v2) | Namespaces por workspace + ontologías conectables — sin relación con este documento |

---

## 10. Addendum 2026-08-27 — la estructura del vault como fuente primaria de aristas

### 10.1 Qué pasó con §3–§6

Las cuatro PRs del rediseño se mergearon (2026-08-19/20) y el backfill (`scripts/backfill_graph_extraction.py`)
se corrió sobre todo el vault. Estado del grafo **antes y después**:

| Métrica | §1 (2026-08-19) | Tras el backfill (2026-08-27) |
|---|---|---|
| Nodos totales | 2.284 | 2.383 |
| Relaciones totales | 312 | **370** |
| Nodos con grado ≥ 1 | ~15% (332) | ~16% (386) |
| Aristas dibujadas por la vista del grafo (top-20 inducido) | — | **10** |

`node_embeddings` quedó poblado (2.354 filas), `chunks.entity_node_ids` al 100% (2.665/2.665): la
infraestructura de §3 y §5 funciona. Lo que no movió la aguja fue la extracción de relaciones en
sí — el criterio de éxito de §8 (que la dispersión baje de "85% aislado") **no se cumplió**.

### 10.2 Causa raíz revisada

§7 anotó como riesgo aceptado que "`llama3.2` es conservador en veredictos". La verificación en
vivo (2026-08-27) mostró algo más terminante: **el modelo no respeta el contrato de salida**.
Pasándole el prompt real de `s8_relations.py::build_relations_prompt` con 6 entidades y un texto
que las relaciona explícitamente, `llama3.2:latest` respondió con prosa, un `Dockerfile` de
ejemplo y varios bloques ` ```bash `, y recién al final un JSON "de ejemplo" con disclaimer.
Recorrido de esa respuesta por el pipeline:

1. `parse_relations_response` → `strip_code_fence` toma el **primer** bloque ` ``` ` encontrado
   (un bloque `bash`, no JSON).
2. `json.loads(...)` lanza `JSONDecodeError`; el `try/except` de `s8` lo trata como "sin
   relaciones" y devuelve `[]`.
3. La extracción completa de ese chunk rinde **cero**, aunque había 3 relaciones válidas.

Esto afecta por igual a las tres aplicaciones del patrón LLM: relaciones intra-documento (`s8`),
relaciones cross-documento (`tasks/cross_doc_relations.py`, que reutiliza el mismo
`build_relations_prompt`/`parse_relations_response`) y el `_default_merge_verdict` de resolución
de entidades.

**No hay mitigación por hardware:** el equipo local no corre un modelo más grande (qwen2.5 y
similares quedan fuera de presupuesto de memoria). Endurecer el parser, re-correr el backfill o
aflojar el gate `_count_mentioned` no crean relaciones que el modelo no puede extraer — solo
evitan perder las pocas respuestas bien formadas. Se descartan como solución al problema de fondo.

### 10.3 Principio del addendum

**El vault ya contiene un grafo hecho a mano que el pipeline descarta.** El conector de Obsidian
(`packages/connectors/src/kos_connectors/obsidian/`) extrae `[[wikilinks]]`, tags y frontmatter;
`pipeline/base.py::bootstrap` los deja en `ParsedDocument.links` / `.keywords` — y
`tasks/graph_sync.py` **nunca los lee**. El grafo se construye 100% desde la salida del LLM.

Medición del vault real (2026-08-27):

| Señal estructural | Presente en el vault | Aristas en Neo4j hoy |
|---|---|---|
| `[[wikilinks]]` | **1.763** en 487 documentos | 0 |
| documentos con tags | 689 | 0 |
| relaciones por extracción LLM (`s7`/`s8` + cross-doc) | — | 370 |

El rediseño invierte la prioridad: **la estructura explícita del vault y la co-ocurrencia
determinística de entidades pasan a ser la fuente primaria de aristas; el LLM local queda como
refuerzo opcional y acotado**, no como única vía. Es la misma lógica de doc 11 §5 ("reglas y
consultas determinísticas, no un loop de planificación LLM") llevada al límite: acá el LLM no es
ni siquiera el veredicto final, porque no es fiable en este hardware.

Esto **no** contradice ADR-0001 (el núcleo no conoce fuentes): las aristas estructurales las
deriva el **conector de Obsidian** y una etapa de pipeline que consume campos ya normalizados de
`ParsedDocument` (`links`, `keywords`, `frontmatter`), no lógica de Obsidian metida en `packages/core`.
Un conector futuro que no tenga wikilinks simplemente entrega `links=[]` y aporta solo §10.5.

### 10.4 Aristas desde la estructura del vault (determinístico, sin LLM)

Nueva etapa en `tasks/graph_sync.py`, después de resolver las entidades del documento y antes de
encadenar el recomendador. Toda la ontología usada ya existe (doc 02 §3, `RELATED_TO`,
`MENTIONS`, `PART_OF`, `AUTHORED_BY`, tipo de nodo `Document`) — **no requiere ADR de ontología**.

1. **Nodo por nota.** Cada documento ingerido tiene un nodo `Document` propio, con
   `canonical_name` derivado del path/título de la nota (`canonicalize()` sobre el stem), `sources`
   = `[doc_id]`. Idempotente por el mismo `merge_node` que ya usa el pipeline. Hoy existen 156
   nodos con label `Document` pero son entidades que el LLM etiquetó así, no nodos de nota
   sistemáticos; esto los vuelve sistemáticos (uno por documento).

2. **Aristas de wikilink.** Por cada destino en `doc.links`, resolver la nota destino a su nodo
   `Document`:
   - Resolución por path exacto primero (el link `Carpeta/Nota` matchea `source_id`), luego por
     título/stem único, luego `canonicalize()` del título. Sin match → se registra como link
     colgante (métrica §10.7), no se crea nodo nuevo.
   - Arista `(:Document {origen}) -[:MENTIONS]-> (:Document {destino})`, `confidence` fija alta
     (p. ej. 0.9 — es una conexión que el usuario escribió a mano), `sources=[doc_id]`,
     `extracted_by="obsidian.wikilink"` (nueva etiqueta en la propiedad `extracted_by` que ya
     existe en `COMMON_RELATION_PROPERTIES`, para poder filtrar/auditar por procedencia).
   - `MENTIONS` es el tipo correcto para "esta nota nombra a esta otra". No se intenta inferir un
     tipo más específico sin evidencia.

3. **Aristas nota ↔ entidad.** Además de conectar notas entre sí, conectar cada nodo `Document`
   con las entidades resueltas de sus propios chunks (`chunks.entity_node_ids`, ya poblado):
   `(:Document) -[:MENTIONS]-> (entidad)`. Esto es lo que saca de aislamiento a las ~2.000
   entidades sueltas: aunque no tengan relación tipada con otra entidad, quedan colgadas de la
   nota que las originó, y las notas están conectadas entre sí por (2).

4. **Aristas de tag / MOC compartido.** Dos notas que comparten un tag, o que ambas linkean el
   mismo nodo `_MOCs/*`, obtienen `(:Document) -[:RELATED_TO]- (:Document)` con `confidence` baja
   (p. ej. 0.4) y `extracted_by="obsidian.shared-tag"`. Con tope por nota (las N notas más
   cercanas por cantidad de tags compartidos) para no generar un componente completo por cada tag
   masivo. Calibrar el tope en implementación; punto de partida N=10, mismo criterio que
   `MAX_CHUNKS_PER_RUN`.

5. **Aristas de frontmatter tipado.** Campos de frontmatter con semántica clara →
   arista tipada, sin LLM:
   - `author:` / `autor:` → `(:Document) -[:AUTHORED_BY]-> (:Person)`.
   - `project:` / `proyecto:`, o carpeta contenedora que sea un proyecto conocido →
     `(:Document) -[:PART_OF]-> (:Project)`.
   - El mapeo campo→relación vive como tabla de constantes en la etapa nueva, no en `packages/core`.

### 10.5 Aristas desde co-ocurrencia de entidades (determinístico, sin LLM)

Independiente del conector (sirve para cualquier fuente). Nueva consulta batch, no por documento:

- Dos entidades que aparecen juntas en el mismo chunk (`chunks.entity_node_ids`) en **≥ K chunks
  distintos de ≥ 2 documentos distintos** → arista `RELATED_TO`, `confidence` en función del
  conteo (p. ej. `min(0.85, 0.4 + 0.05·(n_chunks−K))`), `extracted_by="cooccurrence"`.
- K a calibrar (punto de partida K=3). El piso de "≥ 2 documentos" evita elevar a relación lo que
  es solo una lista dentro de una sola nota.
- Se recalcula en el backfill y, de forma incremental, para los pares tocados por cada
  `graph_sync` (los nodos del documento recién sincronizado contra sus co-ocurrentes).
- `merge_relation` upsertea: si una co-ocurrencia fuerte coincide con una relación que el LLM
  también propuso, se suma evidencia en `sources`, no se duplica.

### 10.6 El LLM local como refuerzo opcional y acotado — DIFERIDO (2026-08-27)

> No construido en esta iteración. §10.4–§10.5 conectan el grafo sin él; su valor real solo se
> puede juzgar midiendo §10.7 con las fuentes determinísticas ya activas. Si se retoma, va como
> tercera pasada del backfill y una rama opcional (config) tras la co-ocurrencia.

No se elimina el LLM, pero deja de ser requisito para tener un grafo conectado. Cuando se use:

- **Solo sobre pares ya surgidos de §10.5** (co-ocurrentes con conteo alto pero sin tipo claro) —
  fan-out acotado, no "todas las relaciones entre estas N entidades".
- **Pregunta binaria, no extracción abierta:** *"Según este texto, ¿'A' USES 'B'? Responde solo
  {"yes": true} o {"yes": false}."* Un tipo de relación y un par por llamada. Salida de un bit —
  dentro de lo que `llama3.2` sí sostiene, y parseable con el mismo fail-safe a `false` de
  `_default_merge_verdict`.
- Con tope por corrida (mismo criterio que `MAX_CONTRADICTION_SEEDS_PER_RUN`).
- Si aún así el rendimiento es pobre, se desactiva por config sin afectar §10.4–§10.5. La extracción
  abierta actual de `s8_relations.py` se mantiene mientras tanto (no rinde, pero tampoco estorba);
  su retiro se evalúa una vez medido §10.7 con las fuentes nuevas activas.

### 10.7 Métricas / criterio de éxito (revisado)

Reemplaza §8 mientras este addendum esté vigente:

- **% de nodos con grado ≥ 1** — objetivo **≥ 60%** tras backfill con §10.4–§10.5 (hoy 16%). La
  mayoría de ese salto debe venir de (3) — entidades colgadas de su nota — y de las aristas de
  wikilink.
- **Aristas por procedencia** (`extracted_by`): `obsidian.wikilink`, `cooccurrence`,
  `obsidian.shared-tag`, `frontmatter`, `llm` — para saber qué fuente sostiene el grafo y poder
  auditar/revertir por origen.
- **Links colgantes**: `[[destinos]]` que no resolvieron a ninguna nota — señal de ruido del
  parser o de notas faltantes, no un error bloqueante.
- Sin cambio en el no-objetivo de §8: no se busca un único componente conectado; un vault personal
  tiene notas genuinamente aisladas.

### 10.8 Backfill

`scripts/backfill_graph_extraction.py` se extiende (o se suma un script hermano) para, además de
re-extraer entidades, poblar §10.4–§10.5 sobre el grafo existente. Como todo es `merge_*`
idempotente por `canonical_name`/tripleta, correrlo de nuevo no duplica. Orden: primero los nodos
`Document` y sus aristas nota↔entidad (barato, sin red salvo Neo4j), después la pasada de
co-ocurrencia (una consulta agregada sobre `chunks`), y solo al final —si se activa— el refuerzo
LLM §10.6.

### 10.9 Riesgos y no-objetivos del addendum

| Riesgo | Tratamiento |
|---|---|
| Los `_MOCs/*` y `_INDEX` generan nodos `Document` con grado altísimo (un MOC linkea decenas de notas) y distorsionan "nodos más conectados" en la vista | Aceptado y esperado — un MOC *es* un hub real del vault. La vista del grafo (doc 13 §5) puede ofrecer un filtro "ocultar hubs" o ponderar por tipo, pero eso es UI, no extracción. |
| Ruido de wikilinks a notas triviales (`pendientes`, `_README`) | `confidence` de la arista + `extracted_by` permiten filtrar; se puede mantener una lista de stems ignorados en la etapa. |
| Co-ocurrencia infla `RELATED_TO` con pares temáticamente vagos | K y el piso de "≥ 2 documentos" son la palanca; se calibra con la métrica de §10.7 antes del backfill completo. |
| Nodo `Document` por nota multiplica el conteo de nodos | Es deseable: son entidades de primera clase del dominio (doc 02 los tiene en la ontología). El conteo de nodos no es una métrica de calidad; el % con grado ≥ 1 sí. |
| ¿"Nodo `Document` sistemático por nota" es decisión estructural? | El tipo ya está en la ontología v1 — no hay tipo nuevo. Si en revisión se considera que *poblarlo sistemáticamente desde el conector* cambia el modelo de dominio lo suficiente, se registra como ADR antes de construir. |

**Fuera de alcance del addendum:**
- Cambiar el modelo LLM local o el mecanismo de veredicto — sin hardware para ello (§10.2).
- Retirar `s8_relations.py` — se evalúa después, con datos (§10.6).
- Un watcher del vault para incrementalidad fina — el encadenamiento actual tras `kos.graph_sync`
  alcanza.
- UI del grafo (filtro de hubs, ponderación por tipo) — es doc 13, no este documento.
