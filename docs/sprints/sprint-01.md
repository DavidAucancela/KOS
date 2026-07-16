# Retro — Sprint 1: "Hola, KOS"

**Cerrado:** 2026-07-14 · **Fase:** 1 (v0.1 — Fundaciones)

## Qué se demostró

- `GET /health` responde 200 con los cinco servicios reales en verde (Postgres, Neo4j, Redis, MinIO, Ollama), checks en paralelo con timeout y `X-Trace-Id` en cada respuesta.
- `make demo`: un texto se embebe con bge-m3 (1024 dims) vía Ollama nativo, se guarda en pgvector y se recupera por similitud coseno (distancia ~0.37 para la pregunta de prueba).
- Round-trip real de Celery: `kos.ping` viaja por Redis y vuelve con timestamp del worker.
- Web (Vite + Tailwind v4 + shadcn/ui): pantalla de estado con polling de `/health`; tipos derivados del cliente OpenAPI generado (`pnpm generate:api`); build, eslint y 3 tests vitest en verde.
- Esquemas del doc 02 en `kos_core.schemas` con `mypy --strict` y 16 tests Python (15 unit + 1 integración de embedding real).
- Migración Alembic 0001 aplicada: tablas `documents`/`chunks` con columna `vector(1024)` e índice HNSW.
- CI real: jobs de Python (ruff/mypy/pytest) y web (eslint/tsc/vitest) sustituyen al placeholder.

## Qué se recortó (deuda visible)

- `integration.yml` (tests @integration con services en CI) pendiente; el test de embedding real corre solo local.
- Auth por token local (doc 06) aún no implementada — `/health` es público, aceptable hasta que exista superficie `/v1`.
- `observability.py` (logs estructurados + OTel) llega en el Sprint 5 según plan.
- El endpoint `GET /v1/ingest/jobs/{id}` (doc 06, Fase 1) se pospone al wiring de ingesta.

## Qué se aprendió

- **iCloud Drive rompe venvs**: el daemon de sincronización de `~/Documents` marca archivos con flag `hidden` y Python ignora los `.pth` ocultos → editables intermitentemente rotos. Solución adoptada: venv fuera del repo (`UV_PROJECT_ENVIRONMENT=$HOME/.venvs/kos`, exportado por el Makefile y documentado en doc 09 §1).
- Con raíz de workspace virtual, `uv run` poda los miembros no referenciados: la raíz debe depender explícitamente de `kos-core/api/workers`.
- SQLAlchemy async necesita `greenlet` explícito en macOS arm64: `sqlalchemy[asyncio]`.
- `kos_core` necesita `py.typed` para que mypy vea sus tipos desde las apps.
