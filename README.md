# KOS — Knowledge Operating System

> Un motor de conocimiento independiente, donde Obsidian es solo uno de los conectores.

KOS construye una **representación digital de tu conocimiento**: ingesta cualquier fuente (Obsidian, PDF, Git, email, web…), la transforma en entidades y relaciones dentro de un grafo de conocimiento, mantiene memoria de largo plazo y razona sobre todo ello mediante agentes coordinados por un planner.

**La pregunta que responde el sistema:**

> ¿Cómo hago que una IA piense utilizando exactamente el mismo conocimiento que tengo yo, pero mejor organizado que mi propia memoria?

## Estado del proyecto

**v0.4 — Memoria y aprendizaje en curso, Sprint 12 cerrado** (2026-08-01, ver [`docs/sprints/`](docs/sprints/)). La API, la web y los workers funcionan end-to-end contra el vault real: ingesta, búsqueda semántica, consulta con evidencia, lectura/corrección/visualización del grafo, propagación del tombstone al grafo, y un pipeline de memoria (episódica → semántica) que audita qué aprendió el sistema. Detalle en [Servicios funcionales](#servicios-funcionales) más abajo y progreso sprint a sprint en [doc 08](docs/08-plan-de-sprints.md).

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
| [09 — Guía de desarrollo y despliegue](docs/09-guia-desarrollo-y-despliegue.md) | Convenciones, entorno local, CI/CD |
| [10 — Estructura del proyecto](docs/10-estructura-del-proyecto.md) | Árbol de archivos objetivo y dónde vive cada cosa |
| [ADRs](docs/adr/) | Architecture Decision Records |

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
│   ├── agents/           # Planner, Retrieval, Graph, Memory… (Fase 4, aún sin código)
│   └── mcp-tools/        # Servidores MCP de herramientas (aún sin código)
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

## Servicios funcionales

Estado real a la fecha (Sprint 12 cerrado), no aspiracional — detalle sprint a sprint en [`docs/sprints/`](docs/sprints/):

- **API (`apps/api`)** — `GET /health` (Postgres/Neo4j/Redis), `/metrics` (Prometheus), `sources` (alta y sincronización de fuentes), `notes` (crear notas desde el chat), `documents` (listado/detalle/chunks), `search` (búsqueda semántica sobre pgvector), `query` (consulta con evidencia, mediada por el planner/pipeline), `graph` (lectura de nodos/vecindario/camino más corto y corrección manual de nodos y relaciones vía `PATCH`/`DELETE`), `memory` (auditoría de memoria vía `GET`/`DELETE /v1/memory`).
- **Web (`apps/web`)** — tres vistas: **Chat** (con panel de citas/evidencia), **Grafo** (visualización de fuerzas del grafo con toggle a tabla de nodos, detalle con vecindario, corrección y rechazo de relaciones) y **Estado** (salud de servicios en vivo).
- **Workers (`apps/workers`)** — ingesta del conector Obsidian, sincronización automática por polling, detección de `doc_type` e intención de plantilla, retiro de evidencia del grafo cuando un documento se tumba (`kos.graph_retire_document`), y el pipeline de memoria (`kos.memory_learn` por consulta respondida, `kos.memory_consolidate` periódico agrupando episódicas repetidas en semánticas).
- **Infraestructura** — Postgres+pgvector, Neo4j (con APOC), Redis, MinIO y Ollama funcionando localmente; un vigía (`make guardian-watch`, activable con `KOS_GUARDIAN_ENABLED=true`) apaga y enciende la infraestructura Docker según uso real.

Pendiente (deuda visible, no en progreso): herramientas MCP de lectura del grafo, consumidores del evento `graph.updated`, recálculo de confianza al perder una fuente (doc 04 §5), zoom/pan y caminos resaltados en la visualización del grafo, entity-linking y búsqueda semántica en memoria (`entities[]` vacío, `GET /v1/memory?q=` es texto simple), memoria sin influir todavía en `/v1/query`, y todo `packages/agents` (Fase 4) en adelante (v0.5 Agentes, v1.0).

## Principios

1. **El núcleo no depende de ninguna fuente.** Obsidian, Notion o Gmail son conectores intercambiables.
2. **El activo es el modelo de conocimiento** (ontología + grafo + memoria), no el LLM.
3. **El LLM nunca accede directamente a los datos**: siempre pasa por el planner.
4. **Local-first**: todo funciona en tu máquina sin enviar conocimiento a terceros.
5. **Docs antes que código**: ninguna fase empieza sin su diseño cerrado.
