# Imagen única para `api` y `workers` (doc 14 §3): mismo código, distinto
# comando de arranque por servicio. En local no se usa — `make dev` sigue
# corriendo procesos nativos (doc 09 §1).

# --- Build del frontend -----------------------------------------------------
# El build estático se sirve desde la propia API (doc 14 §3): un servicio menos
# en Railway y cero coste de frontend.
FROM node:22-alpine AS web
WORKDIR /build
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile
COPY apps/web apps/web
RUN pnpm --filter kos-web build

# --- Build del backend ------------------------------------------------------
FROM python:3.12-slim AS build
# git: `llm-observatory` se instala desde git (ADR-0007), no desde PyPI.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.9.2 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv
COPY pyproject.toml uv.lock ./
COPY packages packages
COPY apps/api apps/api
COPY apps/workers apps/workers
# --frozen: el lock manda; un lock desactualizado debe fallar el build, no
# resolverse solo y desplegar algo distinto a lo probado.
RUN uv sync --frozen --no-dev

# --- Runtime ----------------------------------------------------------------
FROM python:3.12-slim AS runtime
# git se queda en runtime: el drain hace pull/push del repo del vault (doc 14 §5).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /app /app
COPY --from=web /build/apps/web/dist /app/web-dist
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    KOS_WEB_DIST=/app/web-dist \
    KOS_SERVERLESS_MODE=true
EXPOSE 8000

# Servicio `api`. El servicio `workers` sobreescribe el comando en Railway con
# `python -m kos_workers.drain` y su Cron Schedule (ADR-0009).
CMD ["sh", "-c", "uvicorn kos_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
