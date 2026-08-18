# 08 — Plan de implementación por sprints

**Estado:** 🟡 Borrador · **Última actualización:** 2026-08-16

Sprints de **2 semanas**. Cada sprint termina con algo demostrable ("demo o no pasó"). Este plan detalla v0.1 → v0.5 (cerradas) y v1.0 (planificada, sin ejecutar); v1.1 se planifica al cerrar v1.0, con lo aprendido.

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
| 18 | El planner decide: planes dinámicos con LLM, ejecución paralela, Writing agent | ✅ Cerrado 2026-08-15 |
| 19 | El plan se audita: `GET /v1/plans/{id}`, presupuestos y degradación, UI de inspección | ✅ Cerrado 2026-08-16 |
| 20 | El mundo entra: Research agent (MCP externo) + `permissions.py` real para escritura | ✅ Cerrado 2026-08-16 (`obsidian.create_note` a MCP: pospuesto en el sprint, retomado el mismo día vía addendum) |
| 21 | Aprender del plan: Learning agent como post-paso real; memoria empieza a leerse, no solo escribirse | ✅ Cerrado 2026-08-16 |

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

### Sprint 18 — "El planner decide"

**Objetivo:** Planner real (LLM genera el plan) reemplaza el pipeline fijo de `/v1/query`,
eligiendo entre `RetrievalAgent`/`GraphAgent` (Memory queda para Sprint 21), ejecutando en
paralelo los pasos sin dependencias entre sí, fusionando evidencia y delegando la síntesis a un
nuevo `WritingAgent`. Si la generación del plan falla, degrada al pipeline fijo de Sprint 17.

**Demo:** una pregunta que se beneficia de contexto del grafo genera un plan con pasos de
retrieval y grafo; una pregunta factual reduce a 2 pasos equivalentes al pipeline fijo (ahora
decidido por el LLM); forzar un fallo de generación demuestra la caída a `degraded=true` sin
romper la respuesta.

> **Sprint 18 cerrado 2026-08-15**: `packages/core/src/kos_core/schemas/plan.py` (`Plan`,
> `PlanRequest`, `PlanStep` — el tipo que doc 03 §5 nombraba desde el principio pero nunca se
> implementó) + `packages/agents/src/kos_agents/{writing.py,planner/}` (`Planner` con parseo
> tolerante de JSON — mismo patrón que `s7_entities`/`s8_relations` — y `execute_plan` con
> ejecución paralela por dependencias). Dos bugs encontrados y arreglados probando contra infra
> real: evidencia de grafo sin `quote` citable (el LLM veía "evidencia" vacía), y un paso de
> evidencia que falla (LLM propuso un `node_type` inválido) tumbaba toda la request con 500 en vez
> de degradar — ver `docs/deuda-tecnica.md` y la retro. Verificado con `scripts/demo_sprint18.py`
> contra infra real (3 escenarios: plan con grafo, plan factual, fallback). 287 tests unitarios +
> 30 de integración, ruff, `mypy --strict` (core) e import-linter limpios. Retro completa en
> `docs/sprints/sprint-18.md`.

### Sprint 19 — "El plan se audita"

**Objetivo:** cerrar la deuda explícita de Sprint 18 — presupuestos (`Constraints.timeout_s`/
`max_steps`) exigidos de verdad, y el plan generado persistido y auditable vía `GET
/v1/plans/{id}`.

**Demo:** una consulta real a `/v1/query` persiste su plan y `GET /v1/plans/{plan_id}` devuelve
los mismos `steps`/`degraded`; un `plan_id` inexistente da 404; forzar `timeout_s`/`max_steps`
bajos corta la ejecución con `degraded=true` y un `degraded_reason` específico, sin perder las
oleadas ya completadas.

> **Sprint 19 cerrado 2026-08-16**: tabla `kos.plans` (migración `0007_plans.py`) +
> `save_plan`/`get_plan` (`packages/core/.../storage/postgres.py`) + `GET /v1/plans/{plan_id}`
> (`apps/api/.../routes/plans.py`, doc 06 línea 59). `executor.py` exige `timeout_s` (corta al
> tope de una oleada, no cancela tareas en curso) y `max_steps` de verdad —
> `degraded_reason="budget_timeout"`/`"budget_max_steps"`, mismo campo `degraded` que
> `QueryResult` usa desde Sprint 4. Tercera pestaña en `apps/web` (`TracesPage`) para inspeccionar
> un plan por `plan_id`. Verificado con `scripts/demo_sprint19.py` contra infra real (API real,
> `make up`): persistencia, 404, y ambos tipos de degradación por presupuesto. 294 tests
> unitarios + 34 de integración (33 pasan; el fallo restante es el preexistente ya registrado en
> `docs/deuda-tecnica.md`, sin relación con este sprint), ruff, `mypy --strict` (core) e
> import-linter limpios. Retro completa en `docs/sprints/sprint-19.md`.

### Sprint 20 — "El mundo entra"

**Objetivo:** `ResearchAgent` real, conectado al Planner, buscando fuera del vault vía MCP
externo (`github.*`, `web.*`, doc 06 §4) cuando una pregunta lo necesita.

> **Decisión de alcance (2026-08-16)**: la migración de `obsidian.create_note` a herramienta MCP
> con `permissions.py` (la otra mitad del objetivo original de este sprint en la fila de arriba)
> se pospone — decisión explícita del usuario, para no mezclar "conectar el mundo exterior" con
> "reescribir un camino que ya funciona sin bloquear nada". Queda como deuda sin sprint asignado
> todavía (`docs/deuda-tecnica.md`). Fuentes elegidas: GitHub (API pública, sin key para uso
> liviano) y Brave Search (`BRAVE_SEARCH_API_KEY`) para `web.*` — ver doc 06 §4 para el detalle.

- `packages/mcp-tools/src/kos_mcp/tools/github.py`: `github.search_repos`, `github.search_commits`
  contra la API pública de GitHub (`GITHUB_TOKEN` opcional para más cuota).
- `packages/mcp-tools/src/kos_mcp/tools/web.py`: `web.search`, `web.open` contra Brave Search API
  (`BRAVE_SEARCH_API_KEY` requerido — sin key, la tool devuelve un error claro, no falla en
  silencio).
- `packages/agents/src/kos_agents/research.py`: `ResearchAgent` (mismo contrato `Agent` que
  Retrieval/Graph/Writing), evidencia con `source_id`=URL, `connector="github"|"web"`.
- `Planner` suma `research` a su catálogo (doc 03 §3); `executor.py`/`query_service.py` lo
  registran junto a los demás agentes.

**Demo:** una pregunta que necesita contexto externo (ej. "¿qué cambió recientemente en la
librería X que uso?") genera un plan con un paso `research`, con evidencia citando resultados
reales de GitHub/web; una pregunta puramente sobre el vault no lo incluye (el LLM decide, no una
heurística); sin `BRAVE_SEARCH_API_KEY` configurada, un plan que necesita `web.search` degrada en
vez de romper la respuesta.

> **Sprint 20 cerrado 2026-08-16**: `packages/mcp-tools/src/kos_mcp/tools/{github,web}.py`
> (`github.search_repos`/`search_commits` contra la API pública; `web.search` vía Brave Search
> API, `web.open` con extracción de texto por regex) + `ResearchAgent` (`packages/agents`) +
> `Planner`/`query.py` conectándolo al catálogo real. Verificado con `scripts/demo_sprint20.py`
> contra internet real (sin mocks de red): 3 repos reales de GitHub, fetch real de
> `fastapi.tiangolo.com`, y `POST /v1/query` real donde el LLM (llama3.2 local) eligió `research`
> por su cuenta para una pregunta que lo necesitaba — degradó (`degraded=true`) porque el LLM
> omitió `operation` en los inputs del paso, y `executor.py` (Sprint 18) lo absorbió sin romper
> la respuesta, sin necesitar ningún cambio de código nuevo. Un bug encontrado y arreglado
> (tools MCP que devuelven una lista top-level llegan envueltas en `{"result": [...]}`, distinto
> de como devuelven las tools de grafo) — ver `docs/deuda-tecnica.md` y la retro. La migración de
> `obsidian.create_note` a MCP se pospuso por decisión explícita del usuario. 309 tests unitarios
> (25 nuevos), ruff, `mypy --strict` (core) e import-linter limpios. Retro completa en
> `docs/sprints/sprint-20.md`.

### Fuera de plan (pedido directo del usuario, 2026-08-16): migrar `obsidian.create_note` a MCP

Lo que Sprint 20 pospuso por decisión explícita. `obsidian.create_note` pasa a ser una herramienta
MCP real con gate de aprobación en `permissions.py` (`WRITE_TOOLS`), en vez de vivir solo como
lógica directa en `apps/api`. La lógica de renderizado/escritura se promueve a
`packages/core/src/kos_core/notes.py` (`kos_mcp` no puede depender de `apps/api`, doc 09 §2). El
comando `/crear-nota` del chat sigue funcionando igual (convive con la tool, doc 06 §4).

> **Cerrado 2026-08-16**: `packages/core/src/kos_core/notes.py` (promovido desde
> `apps/api/.../notes_service.py`, que queda como re-export delgado para no romper los call sites
> existentes) + `obsidian.create_note` (`packages/mcp-tools/src/kos_mcp/tools/obsidian.py`,
> `confirm=true` requerido) + `WRITE_TOOLS` suma `"obsidian.create_note"` (mismo gate real que
> `memory.store`). Verificado contra el vault real (`/Users/david/Documents/Obsidian Vault`, no
> mockeado): sin `confirm` no escribió nada; con `confirm=true` creó una nota real desde la
> plantilla `Concepto` con contenido renderizado correcto; un segundo intento sobre el mismo
> título falló como se esperaba (nunca sobreescribe); limpieza verificada, sin residuo en el
> vault. 316 tests unitarios (7 nuevos), ruff, `mypy --strict` (core) e import-linter limpios.
> Retro (addendum) en `docs/sprints/sprint-20.md`.

### Sprint 21 — "Aprender del plan"

**Objetivo:** el Learning agent pasa a ser un post-paso real del plan (`Plan.post`, doc 03 §3);
la memoria empieza a leerse en `/v1/query`, no solo a escribirse.

> **Decisiones de alcance (2026-08-16)**: (1) el post-paso de aprendizaje sigue corriendo en
> Celery — no se mueve a una tarea en el proceso de la API — pero la tarea `kos.memory_learn`
> pasa a construir un `LearningAgent` real y llamarlo vía un servidor MCP embebido en el worker
> (mismo patrón que `apps/api` desde Sprint 17), en vez de llamar `kos_core.memory_learn`
> directo. Mantiene la propiedad clave de hoy (no bloquea la respuesta, es durable si el worker
> se cae) y cumple la promesa de doc 04 §1.1 de exponer esto como agente real en Fase 4. (2)
> `memory` se suma al catálogo del Planner con el mismo patrón que `research` (Sprint 20): el LLM
> decide cuándo una pregunta se beneficia de memoria previa, no una heurística fija. Consumir el
> evento `graph.updated` (deuda desde Sprint 9) queda fuera de este sprint — ver doc 03 §3 y
> `docs/deuda-tecnica.md`.

- `packages/core/src/kos_core/schemas/plan.py`: `Plan.post: list[PlanStep]` (nuevo campo).
- `packages/agents/src/kos_agents/learning.py` (nuevo): `LearningAgent`, mismo contrato `Agent`
  que los demás — llama `memory.store` con `confirm=true` (el sistema completando un paso ya
  decidido de antemano, doc 03 §3, no un agente decidiendo escribir algo nuevo por su cuenta).
- `Planner` suma `memory` a su catálogo de evidencia (`MemoryAgent.recall`, ya existe desde
  Sprint 17, standalone) y arma `Plan.post` con un paso `learning` fijo (determinístico, no
  elegido por el LLM — mismo comportamiento incondicional que `kos.memory_learn` ya tiene desde
  Sprint 12) al final de cada plan.
- `apps/workers/src/kos_workers/tasks/memory.py::memory_learn`: en vez de llamar
  `kos_core.memory_learn.learn_from_query_answer` directo, construye un `AppContext`/
  `create_server`/`EmbeddedToolCaller` por invocación (mismo patrón de recursos por-tarea que ya
  usa este módulo) y llama al `LearningAgent` real.
- `apps/workers/pyproject.toml` suma `kos-mcp-tools` y `kos-agents` como dependencias nuevas.

**Demo:** una pregunta que se beneficia de memoria previa (ej. una consulta repetida sobre un
tema ya conversado) genera un plan con un paso `memory` real, visible en `GET /v1/plans/{id}`;
tras responder, `GET /v1/memory` muestra una memoria episódica nueva creada por el `LearningAgent`
real (no por la llamada directa a storage de antes) — verificado contra infra real, sin mocks.

> **Sprint 21 cerrado 2026-08-16 — v0.5 cerrado**: `Plan.post` (migración `0008_plan_post.py`) +
> `LearningAgent` (reusa `MemoryAgent.store`, fuerza `confirm=true`) + `Planner` suma `memory` al
> catálogo y arma `Plan.post` de forma declarativa + `kos.memory_learn` (worker) pasa a llamar al
> `LearningAgent` real vía un servidor MCP embebido, en vez de `kos_core.memory_learn` directo.
> Verificado con `scripts/demo_sprint21.py` contra infra real (API + worker de Celery real, sin
> mocks): un `POST /v1/query` real dejó `Plan.post` declarado y, tras esperar al worker real
> (~13s, latencia normal de Ollama), una memoria episódica nueva visible en `GET /v1/memory`; una
> pregunta sobre "conversaciones previas" hizo que el LLM local eligiera `memory` por su cuenta
> como paso de evidencia. 320 tests unitarios (14 nuevos), ruff, `mypy --strict` (core) e
> import-linter limpios. Retro completa en `docs/sprints/sprint-21.md`.

## v1.0 — Recomendador (Fase 5)

Planificado 2026-08-16, tras cerrar v0.5. Documento habilitante:
[11 — Recomendador e inteligencia proactiva](11-recomendador-e-inteligencia-proactiva.md) (🟡
Borrador). Ver `docs/07-roadmap-versiones.md` para la nota de división v1.0/v1.1.

Cinco sprints — no tres o cuatro optimistas: el patrón histórico de v0.3/v0.4/v0.5 corrió 2x lo
estimado cada vez, y esta vez el alcance ya está recortado a 2 de los 5 tipos de recomendación
originales (doc 11 §4).

| Sprint | Tema | Estado |
|---|---|---|
| 22 | `graph.updated` deja de ser huérfano: emisión real desde sync automático + entrega vía Celery encadenado + tabla `recommendations` + `RecommenderAgent` esqueleto | ✅ Cerrado 2026-08-17 |
| 23 | Lagunas de conocimiento: primer tipo de recomendación real | ✅ Cerrado 2026-08-17 |
| 24 | Contradicciones: segundo tipo de recomendación real | Planificado |
| 25 | Feedback loop: aceptar/descartar + UI mínima | Planificado |
| 26 | Cierre de construcción: verificación en vivo + arranque de la ventana de uso real | Planificado |

### Sprint 22 — "El grafo avisa de verdad"

**Objetivo:** cerrar la deuda fundacional (`docs/deuda-tecnica.md`, "nadie consume el evento
`graph.updated`") antes de construir nada del Recomendador sobre ella — y el hallazgo real de doc
11 §3.1: el camino automático (`kos.graph_sync`) nunca emitió el evento, no solo que nadie lo
escuchaba.

- `kos.graph_sync` encadena `kos.recommend_from_graph_update` (task nuevo) al terminar una
  sincronización exitosa; las correcciones manuales de grafo (`PATCH`/`DELETE /v1/graph/*`)
  encadenan el mismo task.
- Debounce/agrupamiento de `node_ids` en una ventana corta (evita una pasada por nodo en una
  resincronización grande del vault).
- Migración Alembic: tabla `recommendations` (esquema doc 11 §2/§6) — sin lógica de generación
  todavía.
- `RecommenderAgent` esqueleto (`packages/agents/src/kos_agents/recommender.py`): contrato
  `Agent`, sin reglas de negocio.

**Demo:** una sincronización real del vault (o una corrección manual de grafo) dispara el task
nuevo de punta a punta contra infra real, que escribe una fila mínima de prueba en
`recommendations` — probando el cableado disparador→agente antes de construir tipos reales.

> **Sprint 22 cerrado 2026-08-17**: hallazgo real al construir — `GraphUpdated` decía en su propio
> docstring "emitido por `kos.graph_sync`", pero la task nunca lo publicaba (solo lo hacían las
> correcciones manuales de grafo desde Sprint 9). `kos.graph_sync` ahora encadena
> `kos.recommend_from_graph_update`; las correcciones manuales (`PATCH`/`DELETE /v1/graph/*`)
> encadenan el mismo task vía `graph_service.enqueue_recommend` (encola por nombre, la API no
> importa `kos_workers`, doc 09 §2). Debounce con token en Redis: cada disparo reemplaza el token
> vigente, solo el `flush` cuyo token sigue siendo el último programado ejecuta de verdad.
> `RecommenderAgent` (nuevo, `packages/agents`) persiste vía la herramienta MCP nueva
> `recommendations.store` (gate de `permissions.py`, `confirm=True` forzado por el propio agente).
> Verificado contra infra real (migración `0009` aplicada, `recommend_from_graph_update`/
> `recommend_flush` invocados directo con un node_id sintético): escribió una fila real en
> `recommendations`, confirmada por SELECT y luego eliminada (era un smoke test). 349 tests
> unitarios (16 nuevos), ruff, `mypy --strict` (core) e import-linter limpios. Retro completa en
> `docs/sprints/sprint-22.md`.

### Sprint 23 — "Lagunas de conocimiento"

**Objetivo:** primer tipo de recomendación real, generado por reglas sobre el grafo existente.

- Nueva plantilla de `graph.query` (doc 06 §2) para candidatos de laguna vía
  `PREREQUISITE_OF`/`KNOWS`.
- `RecommenderAgent` genera `Recommendation(type="gap")` reales sobre el vault real.
- `GET /v1/recommendations?type=gap&status=`.

**Demo:** una laguna real del vault (`PREREQUISITE_OF` sin `KNOWS` correspondiente) aparece como
recomendación real vía `GET /v1/recommendations`.

> **Sprint 23 cerrado 2026-08-17**: hallazgo real al planificar — nunca existió un nodo `Person`
> que represente al usuario ni ninguna arista `KNOWS` (Sprint 22 pensaba usarla, doc 11 §4). Se
> redefinió "laguna" como nodo `PREREQUISITE_OF` con `confidence < 0.5` (mismo umbral que doc 02
> §4 regla 4 ya usa para decidir qué mostrar) — sin `KNOWS`, decisión explícita, deuda documentada.
> `kos_core.storage.neo4j.gaps_by_prerequisite()` (no una plantilla pública de `graph.query`: el
> único consumidor real llama a `kos_core.storage.neo4j` directo, mismo patrón que
> `kos.memory_learn`) + `has_pending_recommendation()`/`list_recommendations()` en `postgres.py` +
> `_async_recommend` reemplaza el placeholder de Sprint 22 por candidatos reales (tope de 5 por
> pasada) + `GET /v1/recommendations?type=&status=` nuevo. Verificado contra infra real (dos nodos
> `Concept` reales en Neo4j, uno con `confidence=0.2`): generó 1 recomendación real
> (`confidence=0.8`, `priority=1`), confirmada por SELECT y luego eliminada junto a los nodos de
> prueba. 356 tests unitarios + 6 de integración nuevos, ruff, `mypy --strict` (core) e
> import-linter limpios. Retro completa en `docs/sprints/sprint-23.md`.

### Sprint 24 — "Contradicciones"

**Objetivo:** segundo tipo — más costoso que lagunas porque no reutiliza una relación existente
tal cual; requiere comparar afirmaciones, no solo recorrer el grafo.

- Mecanismo de detección de `CONTRADICTS` (doc 11 §5: reglas + paso LLM opcional de redacción, no
  un loop de planificación completo).
- `Recommendation(type="contradiction")` reales sobre el vault.

**Demo:** dos notas reales con afirmaciones contradictorias sobre el mismo concepto generan una
recomendación real.

> Sprint con más riesgo de dividirse en dos (mismo patrón que memoria: Sprint 12 planificado como
> uno terminó necesitando Sprints 13-15) — si la detección de contradicciones no converge en dos
> semanas, cerrar con lo que haya y mover el resto a un sprint 24b, no estirar el sprint.

> **Sprint 24 cerrado 2026-08-17**: a diferencia de lagunas (consulta de grafo pura), no hay forma
> determinística de saber si dos textos se contradicen — candidatos por similitud de embedding
> entre chunks de documentos distintos en una banda intermedia (`similarity_band_chunks`, nuevo en
> `kos_core.storage.search`: piso 0.75, techo 0.92 = mismo valor que `DUPLICATE_THRESHOLD`, por
> encima ya es "duplicado" no contradicción) + veredicto final de un LLM sobre el texto real de
> los dos chunks (`_default_contradiction_verdict`, mismo patrón DI que `_default_merge_verdict`
> de entity resolution — falla a `False` ante ambigüedad, doc 11 §4). Semillas: los `N` chunks más
> recientes con embedding (`recent_seed_chunks`, nuevo en `postgres.py`), misma deuda que
> `gaps_by_prerequisite` (Sprint 23): no acotado por el disparo real que debounceó. Verificado
> contra infra real: chunks reales con afirmaciones opuestas insertados a mano, `_async_recommend`
> real los encontró como candidatos en la banda correcta y llamó al LLM real (Ollama/llama3.2) con
> el texto real — el modelo local, sin embargo, fue conservador y no confirmó la contradicción ni
> siquiera en un caso obvio ("el cielo es azul" vs. "el cielo nunca es azul"), devolviendo JSON
> válido con `contradicts: false` y una explicación real (no un fallo de parseo). El camino
> "sí contradice → crea Recommendation" se verificó con el LLM mockeado (tests unitarios) dado que
> el modelo local no lo disparó en el smoke test — limitación de precisión del modelo chico local,
> no un bug del mecanismo (deuda documentada). 363 tests unitarios + 41 de integración (el único
> fallo es el preexistente `test_busqueda_lexica_vectorial_e_hibrida`, sin relación), ruff,
> `mypy --strict` (core) e import-linter limpios. Retro completa en `docs/sprints/sprint-24.md`.

### Sprint 25 — "Aceptar o descartar"

**Objetivo:** cerrar el loop de feedback (doc 11 §8) y dar visibilidad mínima en la UI.

- `PATCH /v1/recommendations/{id}` (`accepted`/`dismissed` + razón).
- Deduplicación: no regenerar una recomendación descartada con la misma firma
  (`type` + `target_entities`).
- Superficie mínima en `apps/web` (badge/lista, no panel nuevo — doc 11 §7).

**Demo:** descartar una recomendación real evita que la misma laguna/contradicción reaparezca en
la siguiente pasada del Recomendador.

> **Sprint 25 cerrado 2026-08-17**: `PATCH /v1/recommendations/{id}` (`{status: accepted|dismissed,
> reason?}`) nuevo, idempotente contra doble-click (solo actúa sobre `pending`, mismo criterio que
> `archive_memory`). Dedup real: `has_pending_recommendation` (Sprint 23) se renombró a
> `has_active_recommendation` y pasó a bloquear también `accepted`/`dismissed` (antes solo
> `pending` — un descarte dejaba la firma libre para que la siguiente pasada la volviera a
> proponer, bug real de Sprint 23/24 nunca ejercitado hasta ahora). Superficie mínima en
> `apps/web`: `RecommendationsPanel` (nuevo, `features/recommendations/`) embebido en
> `StatusPage` — sin panel/pestaña nueva en el nav, como decidía doc 11 §7 — lista de pendientes
> con Aceptar/Descartar (razón opcional). Verificado contra infra real (API + Postgres reales, sin
> mocks): insertar una recomendación real, `GET` la muestra en `pending`, `PATCH dismissed` con
> razón la resuelve (`resolved_at` seteado) y la saca de la lista de pendientes. 367 tests
> unitarios (4 nuevos: ruta `PATCH`) + 46 de integración (5 nuevos: dedup ampliado +
> `update_recommendation_status`; el único fallo sigue siendo el preexistente
> `test_busqueda_lexica_vectorial_e_hibrida`) + 4 de componente React (`RecommendationsPanel`,
> vitest), ruff, `mypy --strict` (core), import-linter y eslint limpios. Retro completa en
> `docs/sprints/sprint-25.md`.

### Sprint 26 — cierre de construcción + inicio de la ventana de uso real

**Objetivo:** verificar en vivo, no en tests, y arrancar la medición del criterio de salida.

- Registro manual de recomendaciones reales generadas/aceptadas/descartadas (mismo patrón que
  `docs/eval/` para búsqueda).
- Revisión de deuda y actualización de doc 07/08 con lo aprendido, de cara a planificar v1.1.

**Demo:** retro de cierre de construcción. El criterio de salida de v1.0 (≥1 recomendación
útil/semana durante un mes) **no se cumple en este sprint** — arranca a partir de acá y se
verifica con calendario real, no con una demo de sprint. Cerrar v1.0 requiere ~4 semanas
adicionales de calendario después de este sprint antes de poder declarar el criterio cumplido,
aunque el código esté terminado antes.

> **Sprint 26 cerrado 2026-08-18 — construcción de v1.0 completa, ventana de medición iniciada**:
> `scripts/recommendations_report.py` (nuevo) regenera `docs/eval/recomendaciones.md` desde `GET
> /v1/recommendations` real — mismo patrón que `run_eval.py`, calculando "útil" por recomendación
> según doc 11 §10 (`accepted` → útil; `dismissed` → no útil; `pending` → útil recién a los 7 días
> sin descartar). Verificado en vivo con datos sintéticos insertados y limpiados después. Revisión
> de deuda acumulada (Sprints 22-25) contra el criterio de salida: ningún ítem lo bloquea, pero se
> identificó un riesgo real — el veredicto de contradicción conservador (`llama3.2`, deuda ya
> documentada en Sprint 24) puede dejar que el ritmo de "≥1 útil/semana" dependa casi enteramente
> de lagunas, no de ambos tipos por igual. Ventana de medición: 2026-08-18 → 2026-09-18. De paso,
> corrige una regresión real de CI que Sprint 25 había diagnosticado mal como "preexistente"
> (`tsc -b` roto por `PlanOut.post` requerido tras regenerar `schema.d.ts`, nunca ejercitado antes
> porque el tipo generado viejo no tenía el campo) — ver `docs/deuda-tecnica.md`. Retro completa
> con lecciones para v1.1 en `docs/sprints/sprint-26.md`.

## Gestión

- Issues en GitHub con etiquetas por dominio (`ingesta`, `parser`, `grafo`, `memoria`, `agentes`, `ui`, `infra`).
- Un milestone por sprint; el tablero es el project board del repo.
- Al cerrar cada sprint: retro corta escrita en `docs/sprints/` (qué se demostró, qué se recortó, qué se aprendió).
- Deuda pendiente entre retros: [docs/deuda-tecnica.md](deuda-tecnica.md), registro consolidado que se actualiza al cerrar cada sprint.
