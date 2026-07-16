# KOS — Knowledge Operating System

> Un motor de conocimiento independiente, donde Obsidian es solo uno de los conectores.

KOS construye una **representación digital de tu conocimiento**: ingesta cualquier fuente (Obsidian, PDF, Git, email, web…), la transforma en entidades y relaciones dentro de un grafo de conocimiento, mantiene memoria de largo plazo y razona sobre todo ello mediante agentes coordinados por un planner.

**La pregunta que responde el sistema:**

> ¿Cómo hago que una IA piense utilizando exactamente el mismo conocimiento que tengo yo, pero mejor organizado que mi propia memoria?

## Estado del proyecto

**Fase 0 — Fundaciones** (en curso): arquitectura documentada, entorno de desarrollo e infraestructura base. El desarrollo de código comienza en la Fase 1, una vez cerrados los documentos de diseño.

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
│   ├── api/              # FastAPI — API pública y orquestación (Fase 1)
│   ├── web/              # React + TS + Vite + Tailwind + shadcn/ui (Fase 1)
│   └── workers/          # Celery — ingesta, embeddings, grafo (Fase 1)
├── packages/
│   ├── core/             # Modelo de dominio, ontología, contratos internos
│   ├── connectors/       # Conectores de ingesta (Obsidian, PDF, Git…)
│   ├── agents/           # Planner, Retrieval, Graph, Memory… (Fase 4)
│   └── mcp-tools/        # Servidores MCP de herramientas
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

## Arranque rápido (infraestructura)

Requisitos: Docker Desktop y `make`.

```bash
cp .env.example .env      # ajusta credenciales si quieres
make up                   # levanta Postgres, Neo4j, Redis, MinIO y Ollama
make ps                   # estado de los servicios
make down                 # detiene todo
```

Servicios locales:

| Servicio | URL | Credenciales por defecto |
|---|---|---|
| PostgreSQL + pgvector | `localhost:5432` | `kos` / ver `.env` |
| Neo4j Browser | http://localhost:7474 | `neo4j` / ver `.env` |
| Redis | `localhost:6379` | — |
| MinIO Console | http://localhost:9001 | ver `.env` |
| Ollama (nativo en Mac) | http://localhost:11434 | — |

## Principios

1. **El núcleo no depende de ninguna fuente.** Obsidian, Notion o Gmail son conectores intercambiables.
2. **El activo es el modelo de conocimiento** (ontología + grafo + memoria), no el LLM.
3. **El LLM nunca accede directamente a los datos**: siempre pasa por el planner.
4. **Local-first**: todo funciona en tu máquina sin enviar conocimiento a terceros.
5. **Docs antes que código**: ninguna fase empieza sin su diseño cerrado.
