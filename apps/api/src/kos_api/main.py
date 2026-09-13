"""Punto de entrada de la API de KOS: create_app() + registro de routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kos_api import middleware
from kos_api.llm.factory import make_llm_client, make_writing_clients
from kos_api.routes import (
    conversations,
    documents,
    graph,
    health,
    memory,
    memory_proposals,
    metrics,
    notes,
    ops,
    plans,
    query,
    recommendations,
    search,
    sources,
)
from kos_core.config import get_settings
from kos_core.llm.factory import make_embedding_client
from kos_core.observability import configure_logging, configure_tracing
from kos_core.storage import minio as minio_storage
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_core.storage import redis as redis_storage
from kos_mcp.client import EmbeddedToolCaller
from kos_mcp.server import AppContext as MCPAppContext
from kos_mcp.server import create_server as create_mcp_server


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Crea los clientes compartidos (perezosos: no conectan aquí) y los libera al apagar."""
    settings = get_settings()
    configure_logging(level=settings.kos_log_level)
    configure_tracing("kos-api")
    app.state.settings = settings
    app.state.postgres_engine = postgres_storage.create_engine(settings)
    app.state.neo4j_driver = neo4j_storage.create_driver(settings)
    app.state.redis_client = redis_storage.create_client(settings)
    app.state.minio_client = minio_storage.create_client(settings)
    app.state.embedding_client = make_embedding_client(settings)
    # Planner: cliente único (Ollama, o Fallback(OpenAI→Ollama) si cloud está on).
    app.state.llm_client = make_llm_client(settings, task="planner")
    # WritingAgent: local y cloud por separado — su puerta cloud_safe elige por
    # evidencia (ADR-0007). `writing_cloud_llm` es None si cloud está off.
    writing_local, writing_cloud = make_writing_clients(settings)
    app.state.writing_local_llm = writing_local
    app.state.writing_cloud_llm = writing_cloud

    # Servidor MCP embebido (Sprint 17, doc 10 §8): comparte las conexiones de
    # arriba en vez de abrir un segundo pool — los agentes (`packages/agents`)
    # llaman herramientas a través de esta sesión in-memory, nunca a
    # kos_core.storage directo (ADR-0005).
    mcp_context = MCPAppContext(
        settings=settings,
        postgres_engine=app.state.postgres_engine,
        neo4j_driver=app.state.neo4j_driver,
        embedding_client=app.state.embedding_client,
    )
    mcp_server = create_mcp_server(mcp_context)
    async with EmbeddedToolCaller(mcp_server) as tool_caller:
        app.state.tool_caller = tool_caller
        try:
            yield
        finally:
            await app.state.postgres_engine.dispose()
            await app.state.neo4j_driver.close()
            await app.state.redis_client.aclose()
            await app.state.embedding_client.aclose()
            await app.state.llm_client.aclose()
            await app.state.writing_local_llm.aclose()
            if app.state.writing_cloud_llm is not None:
                await app.state.writing_cloud_llm.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="KOS API", version="0.1.0", lifespan=lifespan)
    middleware.install(app)
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(sources.router)
    app.include_router(notes.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(query.router)
    app.include_router(graph.router)
    app.include_router(memory.router)
    app.include_router(plans.router)
    app.include_router(conversations.router)
    app.include_router(recommendations.router)
    app.include_router(memory_proposals.router)
    app.include_router(ops.router)
    _mount_web(app)
    return app


def _mount_web(app: FastAPI) -> None:
    """Sirve el build de `apps/web` desde la propia API (doc 14 §3).

    Se monta **después** de los routers, así `/v1/*` y `/health` siguen ganando.
    El catch-all devuelve `index.html` para que las rutas del cliente (React
    Router) no den 404 al recargar. La credencial la sigue exigiendo el
    middleware: aquí no se abre nada (ADR-0010).
    """
    configured = get_settings().kos_web_dist
    # Ojo con `Path("")`: pathlib lo resuelve a `.`, que sí es un directorio —
    # sin este corte, en local se montaría el directorio de trabajo entero.
    if not configured:
        return
    dist = Path(configured)
    if not dist.is_dir():
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


app = create_app()
