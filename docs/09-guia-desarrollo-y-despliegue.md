# 09 — Guías de desarrollo y despliegue

**Estado:** 🟢 Aprobado (2026-07-14) · **Última actualización:** 2026-07-25

## 1. Entorno local

Requisitos: Docker Desktop, `make`, Python 3.12+ con [uv](https://docs.astral.sh/uv/), Node 20+ con pnpm.

```bash
git clone <repo> && cd kos
cp .env.example .env
make up            # infraestructura (Postgres, Neo4j, Redis, MinIO, Ollama)
make pull-models   # bge-m3 + LLM local
```

En macOS con Apple Silicon, Ollama rinde mucho mejor nativo que en Docker: `brew install ollama`, comentar el servicio `ollama` del compose y apuntar `OLLAMA_BASE_URL` al host.

⚠️ **macOS + iCloud Drive**: si el repo vive bajo `~/Documents` sincronizado con iCloud, el daemon de sincronización marca archivos con el flag `hidden` y Python ignora los `.pth` ocultos, rompiendo los editables del venv de forma intermitente. Por eso el Makefile exporta `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/kos` (venv fuera del árbol sincronizado). Si invocas `uv` directamente sin `make`, exporta esa variable en tu shell o crearás un segundo venv dentro del repo.

Desde el Sprint 1 (cuando existan las apps):

```bash
uv sync                      # dependencias Python (workspace)
pnpm install                 # dependencias JS
make dev                     # api + workers + web en modo desarrollo
```

## 2. Estructura y propiedad del código

| Ruta | Contenido | Regla de dependencia |
|---|---|---|
| `packages/core` | Esquemas, ontología, contratos, clientes de LLM/BD | No depende de nada interno |
| `packages/connectors` | Un paquete por conector | Solo depende de `core` |
| `packages/agents` | Planner y agentes | Solo depende de `core` |
| `packages/mcp-tools` | Servidores MCP | Solo depende de `core` |
| `apps/api` | FastAPI: HTTP, auth, orquestación | Depende de packages |
| `apps/workers` | Celery: ingesta, parser, aprendizaje | Depende de packages |
| `apps/web` | React (aislado, habla solo HTTP) | No importa Python |

Las importaciones que violan esta tabla se rechazan en CI (import-linter).

## 3. Convenciones

### Python

- Python 3.12, tipado estricto (`mypy --strict` en `packages/core`).
- Lint y formato: **ruff** (incluye formateo). Sin black/isort aparte.
- Pydantic v2 para todo esquema; nada de dicts sueltos cruzando fronteras.
- Tests: **pytest**; los tests de cada paquete viven junto al paquete (`tests/`).
- Nombres: módulos `snake_case`, esquemas `PascalCase`, eventos `dominio.pasado` (`document.parsed`).

### TypeScript

- Strict mode; sin `any` no justificado.
- Prettier + ESLint config compartida en la raíz.
- El cliente de la API se genera desde OpenAPI — no se escriben tipos de la API a mano.

### Git

- Trunk-based: ramas cortas → PR → squash a `main`. `main` siempre verde.
- Commits convencionales: `feat(parser): …`, `fix(api): …`, `docs(adr): …`.
- Toda PR que cambie comportamiento referencia el doc/ADR que la ampara, o lo crea.

### Pruebas — pirámide objetivo

1. **Unitarias**: cada etapa del parser, cada esquema, cada regla de confianza.
2. **De contrato**: los eventos y `AgentRequest/Response` validan contra esquemas versionados.
3. **De integración**: pipeline de ingesta contra servicios reales del compose (marcadas `@integration`, corren en CI con services).
4. **De evaluación** (especial de este proyecto): el set de preguntas/respuestas del vault mide la calidad de retrieval y de respuestas en cada PR que toque el pipeline. La calidad es un test más.

## 4. CI/CD (GitHub Actions)

| Workflow | Dispara | Hace |
|---|---|---|
| `ci.yml` | toda PR | ruff + mypy + pytest unit; eslint + tsc + vitest; validación de docs (enlaces rotos, estados) |
| `integration.yml` | PR con etiqueta o merge a main | tests `@integration` con services (Postgres, Neo4j, Redis) |
| `eval.yml` | manual / cambios en parser o retrieval | set de evaluación; publica métricas como comentario en la PR |
| `release.yml` | tag `v*` | build de imágenes Docker + changelog |

La CI corre sobre stubs hasta que exista código; el workflow ya está en `.github/workflows/ci.yml` para que ninguna PR entre sin pasar por ella.

## 5. Configuración y secretos

- Toda config por variables de entorno, tipada con `pydantic-settings` en `core.config`; `.env` local, nunca commiteado.
- Ningún secreto en código, docs ni ADRs. Producción (futura): secretos por entorno del orquestador.
- Feature flags simples por env (`KOS_FEATURE_GRAPH=true`) hasta que haga falta algo mejor.

## 6. Observabilidad

- **Logs**: estructurados (JSON) con `trace_id` en todo el pipeline; nivel por `KOS_LOG_LEVEL`.
- **Trazas**: OpenTelemetry en API, workers y llamadas a LLM (latencia y tokens por etapa).
- **Métricas**: Prometheus (`make obs-up` levanta Prometheus + Grafana). Métricas de negocio desde el inicio: documentos ingeridos, latencia de pipeline, coste de tokens por consulta, tamaño del grafo.

## 7. Despliegue

| Etapa | Estrategia |
|---|---|
| v0.x | Solo local: Docker Compose. El "despliegue" es reproducibilidad: máquina nueva → `make up` → sistema completo en <30 min |
| v1.0 | Imágenes versionadas + compose de producción para self-hosting single-node |
| Post-v1.0 | Kubernetes/Temporal solo cuando haya una razón medida (ver ADRs futuros) |

## 8. Ahorro de recursos: apagado/encendido de la infra por inactividad

`apps/api/src/kos_api/ops/docker_guardian.py` apaga Postgres/Neo4j/Redis/MinIO
cuando no se usan y los enciende bajo demanda al llegar una consulta real.
Ollama queda fuera (corre nativo, no en este compose, y ya descarga sus
modelos de la GPU solo vía su propio `keep_alive`).

Dos mitades, en procesos separados porque ninguna puede depender de que la
otra siga viva:

- **Encendido bajo demanda**: middleware en `kos_api.middleware` (antes del
  `trace_id_middleware`). En cada request que no sea `/health` ni `/metrics`,
  llama a `ensure_stack_up`: si el compose ya está sano, solo registra
  actividad; si no, hace `docker compose up -d` y espera los healthchecks
  (hasta `kos_guardian_start_timeout_seconds`, default 45s) antes de dejar
  pasar la request. Si no llega a tiempo, responde `503` con `Retry-After`.
- **Apagado por inactividad**: `make guardian-watch` corre un vigía aparte
  (`python -m kos_api.ops.docker_guardian watch`) que revisa cada minuto si
  pasaron `kos_idle_stop_minutes` (default 20) desde la última actividad
  registrada, y si es así hace `docker compose stop` (no `down`: conserva
  los contenedores para un arranque rápido). Si nunca hubo actividad
  registrada, no apaga nada — evita interferir con un `docker compose up`
  manual sin pasar por la API.

Apagado por `docker compose stop`: no borra volúmenes, coherente con la
sección 8.

Desactivado por defecto (`kos_guardian_enabled: bool = False`) para no
sorprender a tests ni a quien no tenga `docker compose` a mano. `make dev`
siempre arranca el vigía junto al resto (`guardian-watch`), pero si está
deshabilitado sale de inmediato sin sondear Docker. Para activarlo, en
`.env`:

```bash
KOS_GUARDIAN_ENABLED=true
KOS_IDLE_STOP_MINUTES=20   # opcional, default 20
```

y `make dev` (o `make dev-api` + `make guardian-watch` en paralelo si no
querés levantar workers/web) ya lo aplica.

Coste conocido: la primera request tras estar dormido paga el arranque de
Neo4j (~10-15s); Postgres/Redis/MinIO son casi inmediatos.

## 9. Datos y backups (local)

- Los datos viven en **volúmenes nombrados de Docker** (`kos_postgres_data`, `kos_minio_data`, …), no en bind mounts bajo el repo: en macOS, `~/Documents` sincronizado con iCloud corrompe los datos de Postgres/MinIO (errores EDEADLK) y castiga el rendimiento.
- Backup = `docker run --rm -v kos_minio_data:/data -v "$PWD":/backup alpine tar czf /backup/minio-backup.tgz /data` (con los servicios parados); igual para el resto de volúmenes.
- Los almacenes derivados (pgvector, Neo4j) son **reconstruibles** desde MinIO + fuentes (`kos reindex`); el único dato irrecuperable son los blobs de MinIO y la memoria → prioridad de backup.
