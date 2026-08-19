# 12 — Calidad de extracción: resolución de entidades y relaciones cross-documento

**Estado:** 🟡 Borrador · **Última actualización:** 2026-08-19 · **Habilita:** mejora sobre la
ingesta ya habilitada por [05 — Ingesta y actualización](05-ingesta-y-actualizacion.md) (Fase 1)

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
