# 08 — Plan de implementación por sprints

**Estado:** 🟡 Borrador · **Última actualización:** 2026-07-26

Sprints de **2 semanas**. Cada sprint termina con algo demostrable ("demo o no pasó"). Este plan detalla v0.1 y v0.2; los sprints de versiones posteriores se planifican al cerrar la versión anterior, con lo aprendido.

## Cadencia y reglas

- **Demo al cierre**: cada sprint define su demo por adelantado; si no hay demo, el sprint no se cierra.
- **Un objetivo por sprint**: lo demás es secundario y puede caerse.
- **Deuda visible**: lo que se recorta se anota en el sprint como deuda, no se olvida.
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

## Gestión

- Issues en GitHub con etiquetas por dominio (`ingesta`, `parser`, `grafo`, `memoria`, `agentes`, `ui`, `infra`).
- Un milestone por sprint; el tablero es el project board del repo.
- Al cerrar cada sprint: retro corta escrita en `docs/sprints/` (qué se demostró, qué se recortó, qué se aprendió).
