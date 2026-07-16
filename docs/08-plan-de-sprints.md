# 08 — Plan de implementación por sprints

**Estado:** 🟡 Borrador · **Última actualización:** 2026-07-11

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

### Sprint 4 (semanas 9–10) — "Responde con citas"

**Objetivo:** el caso de uso canónico #1 completo.

- Etapas 5–6 del parser (resumen, keywords)
- `POST /v1/query`: retrieval → contexto → síntesis LLM → respuesta con `evidence[]`
- Contratos `AgentRequest/Response` usados por el pipeline (aunque sea fijo)
- UI: chat + visor de citas que abre el documento original

**Demo:** preguntas reales sobre el vault respondidas con citas clicables. Medición contra el set de evaluación (>90% con ≥1 cita correcta → cierre de v0.2).

### Sprint 5 (semanas 11–12) — "Robustez y PDF/Git"

**Objetivo:** cerrar v0.2 con las tres fuentes y el sistema estable.

- Conectores PDF y Git
- Reingesta incremental por `content_hash`; `kos reindex`
- Observabilidad mínima real: logs estructurados + trazas OTel en el pipeline
- Corrección de lo que el set de evaluación haya revelado

**Demo:** las tres fuentes conviven; borrar/modificar una nota y re-sincronizar funciona.

## v0.3+ (esbozo, se detalla al cerrar v0.2)

| Sprint | Tema probable |
|---|---|
| 6–7 | Extracción de entidades/relaciones + entity resolution |
| 8 | Neo4j + endpoints de grafo + correcciones manuales |
| 9 | Visualización del grafo en la UI |

## Gestión

- Issues en GitHub con etiquetas por dominio (`ingesta`, `parser`, `grafo`, `memoria`, `agentes`, `ui`, `infra`).
- Un milestone por sprint; el tablero es el project board del repo.
- Al cerrar cada sprint: retro corta escrita en `docs/sprints/` (qué se demostró, qué se recortó, qué se aprendió).
