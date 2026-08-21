# KOS — Knowledge Operating System

> Un motor de conocimiento independiente, donde Obsidian es solo uno de los conectores.

KOS construye una **representación digital de tu conocimiento**: ingesta cualquier fuente (Obsidian, PDF, Git, email, web…), la transforma en entidades y relaciones dentro de un grafo de conocimiento, mantiene memoria de largo plazo y razona sobre todo ello mediante agentes coordinados por un planner.

**La pregunta que responde el sistema:**

> ¿Cómo hago que una IA piense utilizando exactamente el mismo conocimiento que tengo yo, pero mejor organizado que mi propia memoria?

## Estado del proyecto

**v1.0 — Recomendador, construcción completa** (2026-08-18, Sprints 22–26, ver [`docs/sprints/`](docs/sprints/)). El sistema ya no solo responde: un `RecommenderAgent` se dispara ante cambios reales del grafo (`graph.updated`, encadenado desde `kos.graph_sync` y desde las correcciones manuales) y propone dos tipos de recomendación — lagunas de conocimiento y contradicciones — con feedback loop real (`PATCH /v1/recommendations/{id}` aceptar/descartar) y deduplicación por firma. **El criterio de salida de v1.0 (≥1 recomendación útil/semana durante un mes) está en ventana de medición real, 2026-08-18 → 2026-09-18** — el código está terminado, pero la versión no se declara cerrada hasta verificar el ritmo real con `scripts/recommendations_report.py` (`docs/eval/recomendaciones.md`).

Se llega ahí sobre **v0.5 — Orquestación de agentes** (cerrado 2026-08-16, Sprints 16–21): `/v1/query` no corre un pipeline fijo — un **Planner** real (LLM) genera un plan dinámico eligiendo entre los agentes `Retrieval`, `Graph`, `Research` (GitHub/web), `Memory` y `Writing`, ejecuta los pasos sin dependencias entre sí en paralelo, y dispara un post-paso de `Learning` que aprende de cada interacción — todo vía un servidor MCP real (`packages/mcp-tools`, 13 herramientas) con gate de aprobación para las de escritura. Si el LLM no puede generar un plan válido, degrada a un pipeline fijo en vez de fallar (`degraded: true`, auditable en `GET /v1/plans/{id}`).

Detalle completo en [Servicios funcionales](#servicios-funcionales) más abajo, progreso sprint a sprint en [doc 08](docs/08-plan-de-sprints.md), y **próximo paso** (no un sprint nuevo, sino tres frentes en paralelo) en [Próximo paso](#próximo-paso).

## Documentación de arquitectura

Toda decisión de diseño vive en [`docs/`](docs/README.md):

| Documento | Contenido |
|---|---|
| [00 — Visión y objetivos](docs/00-vision-y-objetivos.md) | Qué es KOS, para quién, y qué NO es |
| [01 — Arquitectura general](docs/01-arquitectura-general.md) | Los 10 dominios del sistema y sus fronteras |
| [02 — Modelo de dominio y ontología](docs/02-modelo-de-dominio-y-ontologia.md) | Entidades, relaciones y esquema del grafo |
| [03 — Arquitectura de agentes](docs/03-arquitectura-de-agentes.md) | Planner, agentes especializados y coordinación MCP |
| [04 — Memoria y aprendizaje](docs/04-memoria-y-aprendizaje.md) | Tipos de memoria y aprendizaje continuo |
| [05 — Ingesta y actualización](docs/05-ingesta-y-actualizacion.md) | Pipeline de conectores → parser → grafo |
| [06 — APIs y contratos](docs/06-apis-y-contratos.md) | Contratos entre servicios y API pública |
| [07 — Roadmap por versiones](docs/07-roadmap-versiones.md) | v0.1 → v1.0 |
| [08 — Plan de sprints](docs/08-plan-de-sprints.md) | Implementación sprint a sprint |
| [09 — Guía de desarrollo y despliegue](docs/09-guia-desarrollo-y-despliegue.md) | Convenciones, entorno local, CI/CD, monitoreo |
| [10 — Estructura del proyecto](docs/10-estructura-del-proyecto.md) | Árbol de archivos objetivo y dónde vive cada cosa |
| [11 — Recomendador e inteligencia proactiva](docs/11-recomendador-e-inteligencia-proactiva.md) | RecommenderAgent, tipos de recomendación, feedback loop |
| [ADRs](docs/adr/) | Architecture Decision Records |
| [Deuda técnica](docs/deuda-tecnica.md) | Registro vivo de lo pendiente — punto de partida del próximo paso |

## Estructura del monorepo

```
kos/
├── docs/                 # Documentos de arquitectura y ADRs
├── apps/
│   ├── api/              # FastAPI — API pública y orquestación (activo)
│   ├── web/              # React + TS + Vite + Tailwind + shadcn/ui (activo)
│   └── workers/          # Celery — ingesta, embeddings, grafo (activo)
├── packages/
│   ├── core/             # Modelo de dominio, ontología, contratos internos
│   ├── connectors/       # Conectores de ingesta (Obsidian, PDF, Git…)
│   ├── agents/           # Planner, Retrieval, Graph, Research, Memory, Writing, Learning, Recommender (activo)
│   └── mcp-tools/        # Servidor MCP: 13 herramientas + gate de permisos (activo)
├── infra/                # Configuración de servicios (init de Postgres, etc.)
├── docker-compose.yml    # Infraestructura local completa
└── Makefile              # Atajos de desarrollo
```

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | FastAPI + Pydantic |
| Frontend | React + TypeScript + Vite + Tailwind + shadcn/ui |
| Agentes | Arquitectura propia + MCP |
| LLM local | Ollama |
| Embeddings | bge-m3 / nomic-embed-text |
| Vector DB | PostgreSQL + pgvector |
| Grafo | Neo4j |
| Cache / colas | Redis + Celery |
| Almacenamiento | MinIO (S3 compatible) |
| Observabilidad | OpenTelemetry + Prometheus + Grafana |
| Contenedores | Docker Compose (Kubernetes más adelante) |

Las decisiones detrás de cada elección están registradas como [ADRs](docs/adr/).

## Arranque rápido

Requisitos: Docker Desktop, `make`, `uv` y `pnpm`.

```bash
cp .env.example .env    # ajusta credenciales si quieres
make install             # dependencias del workspace (uv + pnpm)
make up                  # levanta Postgres, Neo4j, Redis, MinIO y Ollama
make pull-models         # descarga bge-m3 + el LLM local
make migrate             # aplica migraciones Alembic
make dev                 # API + workers + beat + web + vigía de ahorro de recursos
```

Infraestructura:

| Servicio | URL | Credenciales por defecto |
|---|---|---|
| PostgreSQL + pgvector | `localhost:5432` | `kos` / ver `.env` |
| Neo4j Browser | http://localhost:7474 | `neo4j` / ver `.env` |
| Redis | `localhost:6379` | — |
| MinIO Console | http://localhost:9001 | ver `.env` |
| Ollama (nativo en Mac) | http://localhost:11434 | — |
| Grafana / Prometheus (`make obs-up`) | http://localhost:3000 | ver `.env` |

Aplicación:

| Servicio | URL |
|---|---|
| API (FastAPI, OpenAPI en `/docs`) | http://localhost:8000 |
| Web | http://localhost:5173 |

`make down` detiene todo; `make clean` además borra los volúmenes de datos locales.

El `ResearchAgent` (`github.*`/`web.*`) funciona sin configuración extra para GitHub (cuota liviana
anónima); `web.search`/`web.open` necesitan `BRAVE_SEARCH_API_KEY` en `.env` — sin ella, esos pasos
degradan en vez de romper la respuesta. `GITHUB_TOKEN` es opcional, solo sube la cuota.

## Servicios funcionales

Estado real a la fecha (v1.0 en construcción completa, ventana de medición en curso), no
aspiracional — detalle sprint a sprint en [`docs/sprints/`](docs/sprints/):

- **API (`apps/api`)** — `GET /health` (Postgres/Neo4j/Redis), `/metrics` (Prometheus), `sources` (alta y sincronización de fuentes), `notes` (crear notas desde el chat), `documents` (listado/detalle/chunks), `search` (búsqueda semántica sobre pgvector), `query` (consulta con evidencia, mediada por el Planner real), `graph` (lectura de nodos/vecindario/camino más corto y corrección manual de nodos y relaciones vía `PATCH`/`DELETE`), `memory` (auditoría de memoria vía `GET`/`DELETE /v1/memory`), `plans` (`GET /v1/plans/{id}`: traza completa del plan ejecutado, incluido el post-paso de aprendizaje), `recommendations` (`GET /v1/recommendations` listado paginado, `PATCH /v1/recommendations/{id}` aceptar/descartar).
- **Agentes (`packages/agents`)** — `Planner` (LLM genera un plan JSON dinámico, con reintento y fallback a un plan fijo si no valida), `RetrievalAgent`/`GraphAgent`/`ResearchAgent`/`MemoryAgent` como pasos de evidencia elegidos por el LLM según lo que la pregunta necesite, `WritingAgent` para la síntesis final con citas, `LearningAgent` como post-paso fijo (no elegido por el LLM) que registra cada interacción en memoria episódica, y `RecommenderAgent` — no vive en el plan de `/v1/query`: se dispara vía Celery cuando `graph.updated` ocurre de verdad (sync automático o corrección manual), detecta lagunas de conocimiento y contradicciones, y persiste vía `recommendations.store` (MCP, con dedup por firma `type + target_entities`). Presupuestos de tiempo/pasos por plan (`Constraints`) se hacen cumplir de verdad, con degradación observable (`degraded_reason`).
- **Herramientas MCP (`packages/mcp-tools`)** — 13 herramientas reales tras un único servidor: `vector.search`, `docs.read_document`, `graph.get_node`/`find_path`/`query`, `memory.recall`/`store`, `obsidian.create_note`, `github.search_repos`/`search_commits`, `web.search`/`open`, `recommendations.store`. Las de escritura (`memory.store`, `obsidian.create_note`, `recommendations.store`) exigen `confirm=true` vía un gate real (`permissions.py`), auditado en logs estructurados.
- **Web (`apps/web`)** — cinco features: **Chat** (con panel de citas/evidencia), **Grafo** (visualización de fuerzas con zoom/pan, toggle a tabla de nodos, detalle con vecindario, corrección y rechazo de relaciones), **Trazas** (inspección de un plan ejecutado por `plan_id`), **Recomendaciones** (panel embebido en Estado: pendientes con aceptar/descartar, historial, badge de conteo en el nav) y **Estado** (salud de servicios en vivo).
- **Workers (`apps/workers`)** — ingesta del conector Obsidian, sincronización automática por polling, detección de `doc_type` e intención de plantilla, retiro de evidencia del grafo cuando un documento se tumba, el pipeline de memoria (`kos.memory_learn` construye un `LearningAgent` real sobre un servidor MCP embebido por invocación, `kos.memory_consolidate` agrupa episódicas repetidas en semánticas), y `kos.recommend_from_graph_update` encadenado tras `kos.graph_sync` y tras las correcciones manuales de grafo.
- **Infraestructura** — Postgres+pgvector, Neo4j (con APOC), Redis, MinIO y Ollama funcionando localmente; un vigía (`make guardian-watch`, activable con `KOS_GUARDIAN_ENABLED=true`) apaga y enciende la infraestructura Docker según uso real.

## Próximo paso

Con la construcción de v1.0 completa (código terminado, ventana de medición 2026-08-18 →
2026-09-18 corriendo), el trabajo activo no es un sprint numerado nuevo — son tres frentes en
paralelo sobre [`docs/deuda-tecnica.md`](docs/deuda-tecnica.md):

1. **Deuda técnica** — ítems "sin sprint asignado", evaluando primero el riesgo real de cada uno
   antes de implementar (no todo ítem de deuda es seguro de cerrar sin pensarlo: ver el caso de
   `memory.store` en el catálogo del Planner, evaluado y dejado abierto a propósito por riesgo de
   escritura sin aprobación humana).
2. **Mejoras de calidad** — desambiguación léxica en búsqueda, clasificación de entidades,
   umbrales de similitud sin ajustar con uso real, precisión conservadora del veredicto de
   contradicción con el modelo local.
3. **Monitoreo** — hoy las métricas de negocio (doc 09 §6) cubren ingesta/búsqueda; no hay
   métricas sobre el Planner, los agentes ni el Recomendador (tasa de degradación por tipo,
   distribución de agentes elegidos, latencia por paso, ritmo real de recomendaciones útiles vs.
   lo que reporta `scripts/recommendations_report.py`).

v1.1 (Plataforma: SDK de conectores, API pública estable, empaquetado) no se planifica en sprints
hasta cerrar el criterio de salida de v1.0 — misma regla del roadmap (doc 07: "no se empieza una
versión sin cerrar el criterio de salida de la anterior").

## Principios

1. **El núcleo no depende de ninguna fuente.** Obsidian, Notion o Gmail son conectores intercambiables.
2. **El activo es el modelo de conocimiento** (ontología + grafo + memoria), no el LLM.
3. **El LLM nunca accede directamente a los datos**: siempre pasa por el planner.
4. **Local-first**: todo funciona en tu máquina sin enviar conocimiento a terceros.
5. **Docs antes que código**: ninguna fase empieza sin su diseño cerrado.
