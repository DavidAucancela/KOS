# 08 — Plan de implementación por sprints

**Estado:** 🟡 Borrador · **Última actualización:** 2026-07-26

Sprints de **2 semanas**. Cada sprint termina con algo demostrable ("demo o no pasó"). Este plan detalla v0.1 y v0.2; los sprints de versiones posteriores se planifican al cerrar la versión anterior, con lo aprendido.

## Cadencia y reglas

- **Demo al cierre**: cada sprint define su demo por adelantado; si no hay demo, el sprint no se cierra.
- **Un objetivo por sprint**: lo demás es secundario y puede caerse.
- **Deuda visible**: lo que se recorta se anota en el sprint como deuda, no se olvida — vista
  consolidada en [docs/deuda-tecnica.md](deuda-tecnica.md).
- **Los docs van un sprint por delante del código** que habilitan.

## v0.1 — Fundaciones

### Sprint 0 (semanas 1–2) — "El entorno existe"

**Objetivo:** repo, docs e infraestructura local funcionando.

| Tarea | Entregable |
|---|---|
| Estructura de monorepo + convenciones | este repo |
| Documentos de arquitectura 00–09 (borrador) | `docs/` |
| ADRs 0001–0006 | `docs/adr/` |
| Docker Compose completo + Makefile | `make up` funciona |
| CI esqueleto (lint + validación de estructura) | GitHub Actions verde |
| Revisión y aprobación de docs 00, 01, 02, 05 | estado 🟢 |

**Demo:** `make up` + recorrido por los docs aprobados.

### Sprint 1 (semanas 3–4) — "Hola, KOS"

**Objetivo:** esqueletos de aplicación conectados a la infraestructura.

| Tarea | Entregable |
|---|---|
| Scaffold `apps/api`: FastAPI, config (pydantic-settings), health, OpenAPI | `GET /health` verifica Postgres/Neo4j/Redis |
| Scaffold `packages/core`: `RawDocument`, `ParsedDocument`, `Chunk` | esquemas + tests |
| Scaffold `apps/workers`: Celery conectado a Redis, tarea de prueba | job de ida y vuelta |
| Scaffold `apps/web`: Vite + Tailwind + shadcn/ui, página que llama a `/health` | pantalla de estado |
| Ollama: modelos descargados, wrapper de embeddings + LLM en `packages/core` | test de embedding real |
| Migraciones Alembic iniciales | tablas de documentos/chunks |

**Demo:** la web muestra el estado de todos los servicios; un script embebe un texto con bge-m3 y lo guarda en pgvector.

## v0.2 — Knowledge Core

### Sprint 2 (semanas 5–6) — "El vault entra"

**Objetivo:** conector Obsidian + parser básico end-to-end.

- Interfaz `Connector` + conector Obsidian (`discover`/`fetch`, wikilinks, frontmatter)
- Parser etapas 1–3 (normalización, metadata, chunking por encabezados)
- Ingesta como jobs Celery; blobs a MinIO; documentos/chunks a Postgres
- `GET /v1/documents` + `POST /v1/sources/{id}/sync`

**Demo:** el vault real ingerido completo; documentos y chunks navegables por API.

### Sprint 3 (semanas 7–8) — "Encuentra lo que sé"

**Objetivo:** búsqueda híbrida de calidad.

- Etapa 4: embeddings por lotes hacia pgvector
- Búsqueda léxica (pg_trgm/tsvector) + vectorial + fusión (RRF)
- `POST /v1/search` con evidencia
- Set de evaluación propio (30–50 preguntas del vault con respuesta esperada)

**Demo:** métricas del set de evaluación en búsqueda pura (recall@k).

> **Set de evaluación construido y corrido el 2026-07-16** (más tarde de lo planeado, junto con el cierre de v0.2):
> 38 preguntas sobre el vault real en `docs/eval/preguntas.md`, resultados en `docs/eval/resultados.md`.
> **35/38 = 92.1%** con ≥1 cita correcta — supera el criterio de cierre de v0.2 (>90%) definido en el Sprint 4.
> Los 3 fallos son de desambiguación léxica ("zero" en Zero Conditional vs. Zero Trust; "Supabase" genérico vs. nota
> de Nunna; variantes de formulación casi idénticas con distinto resultado), no de contenido ausente.

### Sprint 4 (semanas 9–10) — "Responde con citas"

**Objetivo:** el caso de uso canónico #1 completo.

- Etapas 5–6 del parser (resumen, keywords)
- `POST /v1/query`: retrieval → contexto → síntesis LLM → respuesta con `evidence[]`
- Contratos `AgentRequest/Response` usados por el pipeline (aunque sea fijo)
- UI: chat + visor de citas que abre el documento original

**Demo:** preguntas reales sobre el vault respondidas con citas clicables. Medición contra el set de evaluación (>90% con ≥1 cita correcta → cierre de v0.2).

> **Criterio de cierre de v0.2 cumplido el 2026-07-16**: 35/38 = 92.1% (ver nota en Sprint 3 y `docs/eval/`).

### Sprint 5 (semanas 11–12) — "Robustez y PDF/Git"

**Objetivo:** cerrar v0.2 con las tres fuentes y el sistema estable.

- Conectores PDF y Git
- Reingesta incremental por `content_hash`; `kos reindex`
- Observabilidad mínima real: logs estructurados + trazas OTel en el pipeline
- Corrección de lo que el set de evaluación haya revelado

**Demo:** las tres fuentes conviven; borrar/modificar una nota y re-sincronizar funciona.

> **Sprint 5 cerrado 2026-07-17**: conectores PDF y Git, tombstone + detección de borrados en
> `kos.sync_source`, `kos reindex` (`make reindex`), logs JSON + trazas OTel (API, workers,
> llamadas a Ollama). 119 tests, lint y mypy --strict limpios. Deuda: métricas Prometheus,
> los 3 fallos de desambiguación del set de evaluación, watchers en tiempo real. Retro completa
> en `docs/sprints/sprint-05.md`. **v0.2 cerrado.**
>
> **Actualización 2026-07-18**: métricas Prometheus (`/metrics` en API y workers, 5 métricas
> reales) y fix de ranking (tercera rama de RRF por título vía `word_similarity`/pg_trgm)
> resueltos. Eval sube a **36/38 = 94.7%**. Detalle en el addendum de
> `docs/sprints/sprint-05.md`.

## v0.3 — Knowledge Graph (Fase 2)

| Sprint | Tema | Estado |
|---|---|---|
| 6 | Núcleo: ontología como código, extracción de entidades/relaciones (s7-s9), entity resolution, escritura real a Neo4j | ✅ Cerrado 2026-07-18 |
| 7 | Fuera de plan (pedido directo del usuario): sincronización automática (polling) + crear notas desde el chat | ✅ Cerrado 2026-07-20 |
| 8 | Fuera de plan (pedido directo del usuario): `doc_type`, detección de intención de plantilla y comando genérico `/crear-nota` — evitar que `/v1/query` fabrique plantillas inexistentes | ✅ Cerrado 2026-07-25 |
| 9 | `/v1/graph/*` + correcciones manuales | ✅ Cerrado 2026-07-26 |
| 10 | Visualización del grafo en la UI | ✅ Cerrado 2026-07-31 |
| 11 | Fuera de plan: tombstone de documentos borrados propagado al grafo (deuda de Sprint 6) | ✅ Cerrado 2026-07-31 |

> **Sprint 6 cerrado 2026-07-18**: `packages/core/src/kos_core/ontology/`, etapas
> `s7_entities`/`s8_relations`/`s9_confidence`, entity resolution (doc 05 §4, 5 pasos) y
> `kos.graph_sync` escribiendo a Neo4j real (idempotente por MERGE). Demo verificada sobre el
> mini_vault de fixtures (9 nodos, 5 relaciones). De paso, fix de generación de títulos
> (`s2_metadata.py`) que venía de la deuda del eval de Sprint 5. 160 tests, lint y
> mypy --strict limpios. Deuda: API/UI de grafo (siguiente sprints), tombstone sin propagar al
> grafo, vault real sin re-sincronizar con el grafo todavía. Retro completa en
> `docs/sprints/sprint-06.md`.

> **Sprint 7 cerrado 2026-07-20**: `kos.sync_all_sources` + Celery beat (polling cada
> `KOS_SYNC_POLL_SECONDS`, doc 05 §2) y `POST /v1/notes` + comando `/nueva-maquina <nombre>` en
> el chat para crear notas desde una plantilla real de `_Templates/` (nueva plantilla
> `MaquinaHTB.md` agregada al vault). Versión mínima de `obsidian.create_note` directamente en
> la API, no como herramienta MCP — desviación documentada en doc 06 §4. También se corrigió
> **un bug crítico** de Sprint 5 (tombstone cruzaba fuentes que comparten conector, rompió
> temporalmente la búsqueda del vault real; recuperado con `kos reindex`). 173 tests, lint y
> mypy --strict limpios. Retro completa en `docs/sprints/sprint-07.md`.

> **Sprint 8 cerrado 2026-07-25**: campo `doc_type` (`"content" | "template"`) en el modelo de
> documento, propagado hasta `/v1/query`; detección de intención de plantilla (`s0`, heurística
> sin LLM) para no fabricar plantillas inexistentes; comando genérico `/crear-nota
> <template>|<folder>|<título>`. Bug real de tipos en SQL textual (`AmbiguousParameter`)
> atrapado solo por prueba manual, no por los 188 tests mockeados — arreglado con `CAST`
> explícito. Ronda de pruebas manuales del usuario (2026-07-25) encontró y corrigió dos huecos
> más: intención de plantilla no cubría órdenes imperativas ("crea una planilla...") y un bug
> preexistente de título con sintaxis de plantilla sin resolver. Backfill de `doc_type` sobre
> `vault-real` completado (698 documentos). Retro completa en `docs/sprints/sprint-08.md`.

> **Sprint 9 cerrado 2026-07-26**: lectura del grafo (`GET /v1/graph/nodes/{id}`, `GET
> /v1/graph/path`, `POST /v1/graph/query` con 3 plantillas seguras) y corrección manual de nodos
> y relaciones (`PATCH`/`DELETE`, protegidas de re-sync vía `locked`/`rejected`, doc 02 regla 5).
> Pantalla mínima de corrección en `apps/web` (tercera vista, junto a Chat/Estado). Bug crítico
> encontrado probando contra el vault real (no por los 217 tests mockeados): corregir el *tipo*
> de un nodo cambia su label real en Neo4j, y un sync posterior que propusiera el tipo viejo creaba
> un duplicado en vez de respetar la corrección — arreglado con un chequeo por `canonical_name`
> sin importar la label, solo para nodos bloqueados. Retro completa en `docs/sprints/sprint-09.md`.

> **Sprint 10 cerrado 2026-07-31**: template `subgraph` (doc 06 §2) — nodos más conectados +
> relaciones activas entre ellos, subgrafo inducido sin Cypher libre — y `GraphCanvas` en
> `apps/web`: layout de fuerzas vía `d3-force` (física) renderizado como SVG por React, con
> toggle Grafo/Tabla sobre el mismo `useGraph()`. Cierra v0.3. Bug real encontrado probando contra
> el vault (patrón que se repite desde Sprint 8): 19 relaciones sin `id` remanentes del backfill
> de Sprint 9 rompían `GET /v1/graph/nodes/{id}` con 500 — backfileadas del mismo modo. Retro
> completa en `docs/sprints/sprint-10.md`.

> **Sprint 11 cerrado 2026-07-31**: `document.deleted` pasó de evento definido-pero-nunca-emitido
> a estar realmente conectado — `kos.sync_source` lo publica y encadena `kos.graph_retire_document`
> (nueva task) por cada documento tumbado. `neo4j_storage.retire_document` saca el `doc_id` de
> `sources[]` de nodos/relaciones y borra lo que queda sin ninguna fuente, protegiendo lo `locked`.
> Deuda de Sprint 6, reafirmada en las retros de Sprint 9 y 10, resuelta acá. Sin recálculo de
> `confidence` en lo que sobrevive (doc 04 §5) — no hay fórmula definida todavía, deuda visible.
> Retro completa en `docs/sprints/sprint-11.md`.

## v0.4 — Memoria y aprendizaje (Fase 3)

| Sprint | Tema | Estado |
|---|---|---|
| 12 | Pipeline de memoria: escritura episódica, consolidación a semántica, auditoría (`GET`/`DELETE /v1/memory`) | ✅ Cerrado 2026-08-01 |

> **Sprint 12 cerrado 2026-08-01**: tabla `memory_items` (Postgres + pgvector), `kos.memory_learn`
> (encolada sin bloquear desde `POST /v1/query`, doc 04 §1.1: pipeline fijo de Celery, no agentes
> reales) escribe una memoria episódica por consulta respondida; `kos.memory_consolidate` (Celery
> beat, `KOS_MEMORY_CONSOLIDATION_HOURS`) agrupa ≥3 episódicas con similitud >0.92 en una
> semántica determinística (sin LLM), marcando las episódicas `superseded_by` sin borrarlas.
> `effective_salience` calcula el decaimiento exponencial al leer, no en un job aparte. `GET
> /v1/memory?type=&q=` y `DELETE /v1/memory/{id}` (archivado, doc 06 §2) para auditar. Verificado
> extremo a extremo contra infra real: una consulta real a `/v1/query` quedó visible como memoria
> episódica vía `GET /v1/memory`. Deuda visible: sin entity-linking (`entities[]` queda vacío),
> sin recálculo de confianza al perder una fuente (heredada de Sprint 11), demo de consolidación
> con 3 preguntas repetidas cubierta por tests (no en vivo — Ollama local ocupado por la
> sincronización real del vault durante la verificación). Retro completa en
> `docs/sprints/sprint-12.md`.

| 13 | Entity-linking en memoria (`entities[]`) — deuda de Sprint 12 | ✅ Cerrado 2026-08-14 |
| 14 | Recálculo de `confidence` al perder una fuente (grafo + memoria) — deuda de Sprint 11/12 | ✅ Cerrado 2026-08-15 |
| 15 | Cierre de v0.4: demo de consolidación en vivo + deuda restante | ✅ Cerrado 2026-08-15 |

### Sprint 13 — "La memoria conoce el grafo"

**Objetivo:** `kos.memory_learn` deja de escribir `entities=[]` a secas.

- `entities[]` se resuelve buscando qué nodos del grafo comparten alguna `sources[]` con la
  memoria (relación `MENTIONS` que `graph_sync` ya construyó) — sin extracción LLM nueva, sin
  latencia adicional en `POST /v1/query` (doc 04 §2, decidido 2026-08-13).
- Sin cambio de esquema: `MemoryItem.entities` ya existe (`packages/core/src/kos_core/schemas/memory.py:21`).

**Demo:** una consulta real sobre el vault que use evidencia de nodos conocidos deja una memoria
episódica con `entities[]` no vacío, visible en `GET /v1/memory`.

> **Sprint 13 cerrado 2026-08-14**: `find_node_ids_by_sources` (`packages/core/.../storage/neo4j.py`)
> + `kos.memory_learn` resolviendo `entities[]` vía `resolve_entities` inyectado (mismo patrón que
> `embed`). Verificado en vivo: `"¿qué es Next.js?"` contra el vault real dejó una memoria con
> `entities[]` de 33 node_ids que comparten fuente con la evidencia. 246 tests, ruff y
> `mypy --strict` (core) limpios. Retro completa en `docs/sprints/sprint-13.md`.

### Sprint 14 — "La confianza se ajusta"

**Objetivo:** implementar la fórmula de recálculo de `confidence` decidida en doc 04 §5, para
grafo y memoria por igual.

- Migración de esquema: `source_confidences[]` (array paralelo a `sources[]`) en nodos y
  relaciones de Neo4j; `MemoryItem.sources` pasa de `list[str]` a `list[{doc_id, confidence}]`
  en Postgres (JSONB) — migración Alembic + backfill de datos existentes.
- Fórmula `confidence_nueva = min(1.0, max(confidence_base_i restantes) + ALIAS_BOOST × (n_restantes − 1))`
  aplicada en `retire_document` (`packages/core/src/kos_core/storage/neo4j.py:382`, deuda de
  Sprint 11) y en el tombstone de memoria (Sprint 12).
- Umbral de alerta: `confidence_nueva < 0.3` marca candidato a poda/revisión (distinto del
  umbral de auto-poda `<0.2`, doc 02 §4 regla 4).

**Demo:** borrar un documento que es una de varias fuentes de un nodo y de una memoria; el
`confidence` de lo que sobrevive baja según la fórmula, visible en `GET /v1/graph/nodes/{id}` y
`GET /v1/memory`.

> **Sprint 14 cerrado 2026-08-15**: `source_confidences[]` (array paralelo en Neo4j) y
> `SourceRef` (`{doc_id, confidence}` en Postgres/JSONB); recálculo en `retire_document`
> (grafo) y nueva `retire_memory_sources`/`kos.memory_retire_document` (memoria, encadenada
> desde `kos.sync_source`, antes no existía esa propagación). `prune_candidate` (`confidence <
> 0.3`) expuesto en grafo y memoria. Verificado en vivo con datos sintéticos disparados por el
> worker Celery real: `confidence` bajó de 0.9 a 0.75 en nodo y memoria tras retirar una de tres
> fuentes, visible en `GET /v1/graph/nodes/{id}` y `GET /v1/memory`. 246 tests + 16 de
> integración nuevos/tocados, ruff y `mypy --strict` (core) limpios. Retro completa en
> `docs/sprints/sprint-14.md`.

### Sprint 15 — cierre de v0.4

**Objetivo:** verificar en vivo lo que Sprint 12 dejó cubierto solo por tests, y cerrar v0.4.

- Correr `kos.memory_consolidate` contra 3 preguntas repetidas reales sobre el vault, sin
  contención de Ollama con la sincronización del vault.
- Revisar deuda restante de v0.4 y actualizar el roadmap (doc 07) hacia v0.5 (Fase 4).

**Demo:** consolidación real observada en `GET /v1/memory` (episódicas → `superseded_by` una
semántica nueva). Retro de cierre de v0.4.

> **Sprint 15 cerrado 2026-08-15 — v0.4 cerrado**: la misma pregunta real ("¿qué es FastAPI?")
> enviada 3 veces a `/v1/query` generó 3 episódicas lo bastante similares para que
> `kos.memory_consolidate` (worker Celery real) las agrupara en una semántica nueva, con las 3
> marcadas `superseded_by` — verificado en `GET /v1/memory`, sin data sintética (preguntas reales
> sobre el vault real). Deuda de v0.4 revisada con el usuario: sin UI de auditoría de memoria en
> `apps/web` queda documentada, no bloquea el cierre (decisión explícita 2026-08-15). Roadmap
> (doc 07) actualizado con la nota de cierre de v0.4. Retro completa en
> `docs/sprints/sprint-15.md`.

## v0.5 — Orquestación de agentes (Fase 4)

| Sprint | Tema | Estado |
|---|---|---|
| 16 | Servidor MCP real: 7 herramientas de lectura/escritura envolviendo lo ya existente | ✅ Cerrado 2026-08-15 |
| 17 | Los agentes existen: Retrieval/Graph/Memory reales consumiendo las herramientas MCP | ✅ Cerrado 2026-08-15 |
| 18 | El planner decide: planes dinámicos con LLM, ejecución paralela, Writing agent | 🟡 Planificado |
| 19 | El plan se audita: `GET /v1/plans/{id}`, presupuestos y degradación, UI de inspección | 🟡 Planificado |
| 20 | El mundo entra: Research agent (MCP externo) + `permissions.py` real para escritura | 🟡 Planificado |
| 21 | Aprender del plan: Learning agent como post-paso real; memoria empieza a leerse, no solo escribirse | 🟡 Planificado |

Estimación original de doc 07 (6-8 semanas): revisada a 6 sprints (~12 semanas) al planificar
Sprint 16 — no había ni una línea de código de MCP/agentes, la estimación asumía más base
construida de la que había.

### Sprint 16 — "Las herramientas hablan MCP"

**Objetivo:** primer servidor MCP real (`packages/mcp-tools`, doc 10 §8, ADR-0005), envolviendo
las capacidades de lectura ya existentes (`vector.search`, `docs.read_document`,
`graph.get_node`/`find_path`/`query`, `memory.recall`) más la primera herramienta de escritura
real (`memory.store`) con su gate de permisos — sin tocar el pipeline fijo de `/v1/query` todavía
(eso es Sprint 17).

**Demo:** un cliente MCP lista las 7 herramientas y ejecuta `graph.get_node` contra el grafo real,
mismo resultado que `GET /v1/graph/nodes/{id}`; `memory.store` sin `confirm` devuelve la
explicación de aprobación pendiente, con `confirm=true` escribe la memoria real y devuelve su
`memory_id`.

> **Sprint 16 cerrado 2026-08-15**: servidor MCP real (`MCPServer`, transporte stdio) + 7
> herramientas + `permissions.py` (gate real para escrituras) + 4 promociones de lógica de
> `apps/*` a `packages/core` (garantizan por construcción que MCP y la API den el mismo resultado)
> + import-linter en CI (gap real entre doc 09 §2 y lo que CI verificaba, cerrado). De paso,
> arreglado un bug heredado de Sprint 14 (`GET /v1/memory` rompía sobre memorias previas a la
> migración de esquema — backfill de 5 filas). Verificado con `scripts/demo_sprint16.py`: servidor
> real como subproceso stdio contra infra real. 283 tests (255 unitarios + 28 de integración),
> ruff, `mypy --strict` (core) e import-linter limpios. Retro completa en
> `docs/sprints/sprint-16.md`.

### Sprint 17 — "Los agentes existen"

**Objetivo:** `RetrievalAgent` reemplaza la lógica de retrieval que `/v1/query` llamaba directo
sobre `kos_core.storage.search`, ahora vía la herramienta MCP `vector.search` (ADR-0005).
`GraphAgent`/`MemoryAgent` se construyen y prueban reales contra infra, pero standalone — sin
conectar a `/v1/query` todavía (esperan al Planner de Sprint 18, que decide cuándo corresponde
cada uno; conectarlos ahora con una heurística casera se tiraría apenas exista el Planner real).

**Demo:** `/v1/query` real da la misma respuesta que antes del refactor, pero el paso de
retrieval corre vía `RetrievalAgent`/MCP; `GraphAgent`/`MemoryAgent` funcionan contra infra real
de forma standalone (`scripts/demo_sprint17.py`).

> **Sprint 17 cerrado 2026-08-15**: `packages/agents` (`kos_agents`) nuevo, solo depende de
> `core` (`ToolCaller`/`Agent` como `Protocol`, duck typing — evita que los agentes importen
> `kos_mcp` directo). `vector.search` (MCP) extendida con `mode`/degradación/`confidence` para que
> `RetrievalAgent` no perdiera comportamiento; `kos_mcp.server.create_server()` ahora acepta un
> `AppContext` externo y nuevo `kos_mcp/client.py::EmbeddedToolCaller` — `apps/api` embebe el
> servidor MCP compartiendo sus propias conexiones, sin un segundo pool. Dos bugs propios
> encontrados y arreglados en el momento (colisión de `tests/__init__.py`, fuga de tests
> pegándole a Ollama real por captura estática del embedder) — ver `docs/deuda-tecnica.md`.
> Verificado con `POST /v1/query` real (servidor real, no `TestClient`) y
> `scripts/demo_sprint17.py`. 271 tests unitarios + 30 de integración, ruff, `mypy --strict`
> (core) e import-linter limpios. Retro completa en `docs/sprints/sprint-17.md`.

## Gestión

- Issues en GitHub con etiquetas por dominio (`ingesta`, `parser`, `grafo`, `memoria`, `agentes`, `ui`, `infra`).
- Un milestone por sprint; el tablero es el project board del repo.
- Al cerrar cada sprint: retro corta escrita en `docs/sprints/` (qué se demostró, qué se recortó, qué se aprendió).
- Deuda pendiente entre retros: [docs/deuda-tecnica.md](deuda-tecnica.md), registro consolidado que se actualiza al cerrar cada sprint.
