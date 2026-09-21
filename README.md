# KOS — Knowledge Operating System

A source-independent knowledge engine. It ingests your notes and documents, turns them into a
knowledge graph with long-term memory, and answers questions through a team of agents — always
with evidence. Obsidian is just one connector.

> How do I make an AI think with exactly the same knowledge I have, but better organized than my
> own memory?

**Status:** v1.0 feature-complete, but **not closed** — the exit criterion (≥1 useful
recommendation per week) was measured on 2026-09-19 and was not met. Details in
[`docs/07-roadmap-versiones.md`](docs/07-roadmap-versiones.md). Managed deployment on Railway is
live; data migration is next ([doc 14](docs/14-despliegue-en-railway.md)).

## What it does

| Category | Summary |
|---|---|
| **Ingestion** | Connectors for Obsidian, PDF and Git feed a pipeline that parses, chunks and embeds documents. Automatic polling sync; removed documents are retired from the graph. |
| **Knowledge graph** | Entities and relations in Neo4j. Connectivity comes mostly from vault structure (`[[wikilinks]]`, shared tags, frontmatter, co-occurrence), with the LLM as an optional booster. Manual correction of nodes and relations. |
| **Search & Q&A** | Semantic search over pgvector. `POST /v1/query` returns an answer with `evidence[]` — an answer without evidence is a bug. |
| **Agents** | An LLM **Planner** builds a dynamic plan and picks among Retrieval, Graph, Research (GitHub/web), Memory and Writing agents; independent steps run in parallel. If no valid plan can be produced, it degrades to a fixed pipeline. Every plan is auditable at `GET /v1/plans/{id}`. |
| **Memory** | A Learning agent records each interaction as episodic memory; a consolidation job groups repeats into semantic memory. Items can be audited, corrected and locked by hand. |
| **Recommendations** | A Recommender agent reacts to real graph changes, detects knowledge gaps and contradictions, and learns from accept/dismiss feedback. Deduplicated by signature. |
| **Tools (MCP)** | 16 tools behind a single MCP server (vector, docs, graph, memory, GitHub, web, Obsidian, recommendations). Write tools require `confirm=true` through a real permission gate — the LLM never approves its own writes. |
| **Interface** | React web app with Chat + citations, Graph explorer, Plan traces, Memory audit, Metrics and Status (with recommendations). |
| **Observability** | Structured logs, OpenTelemetry traces, Prometheus `/metrics` including business metrics for planner, agents and recommender (computed from Postgres on each scrape). |
| **LLM providers** | Local-first with Ollama. Cloud providers are opt-in per task (Planner and Writing only); ingestion, graph extraction and embeddings stay local by default. |
| **Deployment** | Local Docker Compose, or a low-cost managed mode on Railway + Supabase + Aura + R2 with a cron-driven worker so the API can sleep. |

## Architecture

```
apps/
  api/          FastAPI — public API and orchestration
  web/          React + TypeScript + Vite + Tailwind + shadcn/ui
  workers/      Celery — ingestion, embeddings, graph sync, memory, recommendations
packages/
  core/         Domain model, ontology, schemas, storage, observability
  connectors/   Source connectors (Obsidian, PDF, Git)
  agents/       Planner + Retrieval, Graph, Research, Memory, Writing, Learning, Recommender
  mcp-tools/    MCP server, tools and permission gate
docs/           Architecture documents, ADRs, sprint history
infra/          Service configuration
scripts/        Reports, backfills, evals, demos
```

The core knows no concrete source ([ADR-0001](docs/adr/0001-nucleo-independiente-de-fuentes.md));
everything crossing a boundary uses schemas from `packages/core`.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Pydantic, Celery |
| Frontend | React, TypeScript, Vite, Tailwind, shadcn/ui |
| Agents | Custom orchestration + MCP |
| LLM / embeddings | Ollama (local), bge-m3 |
| Vector store | PostgreSQL + pgvector |
| Graph | Neo4j |
| Queue / cache | Redis |
| Object storage | MinIO (S3-compatible) |
| Observability | OpenTelemetry, Prometheus, Grafana |
| Packaging | uv + pnpm workspaces, Docker |

## Quick start

Requirements: Docker Desktop, `make`, `uv`, `pnpm`, and Ollama.

```bash
cp .env.example .env    # adjust credentials if you want
make install            # workspace dependencies (uv + pnpm)
make up                 # Postgres, Neo4j, Redis, MinIO, Ollama
make pull-models        # bge-m3 + the local LLM
make migrate            # Alembic migrations
make dev                # API + workers + beat + web
```

| Service | URL |
|---|---|
| API (OpenAPI at `/docs`) | http://localhost:8000 |
| Web | http://localhost:5173 |
| Neo4j Browser | http://localhost:7474 |
| MinIO Console | http://localhost:9001 |
| Grafana / Prometheus (`make obs-up`) | http://localhost:3000 |

Other useful targets: `make test`, `make lint`, `make down`, and `make clean` (⚠️ deletes local
data volumes). Run `make help` for the full list.

Optional: `BRAVE_SEARCH_API_KEY` enables `web.search`/`web.open`; `GITHUB_TOKEN` raises the GitHub
quota. Without them those steps degrade instead of failing.

## Documentation

Design lives in [`docs/`](docs/README.md) (written in Spanish). Start here:

| Topic | Documents |
|---|---|
| Vision & architecture | [00 Vision](docs/00-vision-y-objetivos.md) · [01 Architecture](docs/01-arquitectura-general.md) · [02 Domain model](docs/02-modelo-de-dominio-y-ontologia.md) |
| Agents, memory & ingestion | [03 Agents](docs/03-arquitectura-de-agentes.md) · [04 Memory](docs/04-memoria-y-aprendizaje.md) · [05 Ingestion](docs/05-ingesta-y-actualizacion.md) · [11 Recommender](docs/11-recomendador-e-inteligencia-proactiva.md) · [12 Extraction quality](docs/12-calidad-de-extraccion-de-entidades-y-relaciones.md) |
| API & UI | [06 APIs](docs/06-apis-y-contratos.md) · [13 User interface](docs/13-interfaz-de-usuario.md) |
| Delivery | [07 Roadmap](docs/07-roadmap-versiones.md) · [08 Sprint plan](docs/08-plan-de-sprints.md) · [09 Dev & deploy guide](docs/09-guia-desarrollo-y-despliegue.md) · [10 Project structure](docs/10-estructura-del-proyecto.md) |
| Deployment & LLM providers | [14 Railway](docs/14-despliegue-en-railway.md) · [15 Multi-provider LLM](docs/15-multiproveedor-llm.md) |
| Decisions & backlog | [ADRs](docs/adr/) · [Technical debt](docs/deuda-tecnica.md) |

## Principles

1. **The core is source-independent.** Obsidian, Notion or Gmail are interchangeable connectors.
2. **The asset is the knowledge model** (ontology + graph + memory), not the LLM.
3. **The LLM never touches data directly** — the Planner always mediates.
4. **Local-first.** Everything runs on your machine; cloud is opt-in.
5. **Docs before code.** No phase starts without an approved design.
