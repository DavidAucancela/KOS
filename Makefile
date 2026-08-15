# KOS — atajos de desarrollo

# El venv vive FUERA del repo: ~/Documents está sincronizado con iCloud Drive y su
# daemon marca archivos con el flag "hidden", lo que rompe los .pth del venv
# (Python ignora los .pth ocultos). Ver docs/09 §1.
export UV_PROJECT_ENVIRONMENT := $(HOME)/.venvs/kos

.PHONY: up down ps logs clean pull-models obs-up install dev dev-api dev-workers dev-beat dev-web \
        migrate lint test test-integration demo reindex guardian-watch mcp-inspect mcp-demo \
        agents-demo help

up: ## Levanta la infraestructura base (Postgres, Neo4j, Redis, MinIO, Ollama)
	docker compose up -d

down: ## Detiene todos los servicios
	docker compose down

ps: ## Estado de los servicios
	docker compose ps

logs: ## Logs de todos los servicios (make logs s=postgres para uno)
	docker compose logs -f $(s)

obs-up: ## Levanta también Prometheus y Grafana
	docker compose --profile observability up -d

pull-models: ## Descarga los modelos (Ollama nativo; cae a Docker si no está)
	ollama pull bge-m3 || docker exec kos-ollama ollama pull bge-m3
	ollama pull llama3.2 || docker exec kos-ollama ollama pull llama3.2

install: ## Instala las dependencias (workspace uv + pnpm)
	uv sync --all-packages
	pnpm install

dev: ## API + workers + beat + web + vigía de ahorro de recursos (Ctrl-C para salir; doc 09 §8)
	$(MAKE) -j5 dev-api dev-workers dev-beat dev-web guardian-watch

dev-api: ## Solo la API (http://localhost:8000)
	uv run uvicorn kos_api.main:app --reload --port 8000

dev-workers: ## Solo los workers Celery
	uv run celery -A kos_workers.celery_app worker --loglevel=INFO

dev-beat: ## Solo el scheduler de Celery (sincronización automática, doc 05 §2)
	uv run celery -A kos_workers.celery_app beat --loglevel=INFO

dev-web: ## Solo la web (http://localhost:5173)
	pnpm --filter kos-web dev

migrate: ## Aplica las migraciones de Postgres (Alembic)
	uv run alembic -c packages/core/alembic.ini upgrade head

lint: ## Ruff + mypy (core estricto) + reglas de dependencia + eslint web
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy --strict packages/core/src/kos_core
	uv run lint-imports
	pnpm --filter kos-web lint

test: ## Tests unitarios (Python + web)
	uv run pytest
	pnpm --filter kos-web test

test-integration: ## Tests @integration (requieren make up + Ollama con modelos)
	uv run pytest -m integration -o addopts=""

demo: ## Demo del Sprint 1: embedding con bge-m3 guardado y consultado en pgvector
	uv run python scripts/demo_sprint1.py

reindex: ## kos reindex: reconstruye los derivados desde MinIO + fuentes (doc 05 §5; s=nombre opcional)
	uv run python scripts/kos_reindex.py $(if $(s),--source $(s),)

guardian-watch: ## Vigía de ahorro de recursos: apaga la infra Docker sin uso (doc 09 §9; requiere KOS_GUARDIAN_ENABLED=true)
	uv run python -m kos_api.ops.docker_guardian watch

mcp-inspect: ## Abre el MCP Inspector contra el servidor de herramientas (Sprint 16, smoke test manual)
	uv run mcp dev packages/mcp-tools/src/kos_mcp/server.py

mcp-demo: ## Demo del Sprint 16: las 7 herramientas MCP contra infra real (requiere make up + vault sincronizado)
	uv run python scripts/demo_sprint16.py

agents-demo: ## Demo del Sprint 17: RetrievalAgent en /v1/query + GraphAgent/MemoryAgent standalone (requiere make up + dev-api)
	uv run python scripts/demo_sprint17.py

clean: ## Detiene servicios y ELIMINA todos los datos locales (volúmenes Docker)
	docker compose down -v
	rm -rf .data

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
