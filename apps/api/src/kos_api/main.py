"""Punto de entrada de la API de KOS: create_app() + registro de routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from kos_api import middleware
from kos_api.routes import documents, health, query, search, sources
from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient, OllamaLLMClient
from kos_core.storage import minio as minio_storage
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_core.storage import redis as redis_storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Crea los clientes compartidos (perezosos: no conectan aquí) y los libera al apagar."""
    settings = get_settings()
    app.state.settings = settings
    app.state.postgres_engine = postgres_storage.create_engine(settings)
    app.state.neo4j_driver = neo4j_storage.create_driver(settings)
    app.state.redis_client = redis_storage.create_client(settings)
    app.state.minio_client = minio_storage.create_client(settings)
    app.state.embedding_client = OllamaEmbeddingClient(settings)
    app.state.llm_client = OllamaLLMClient(settings)
    try:
        yield
    finally:
        await app.state.postgres_engine.dispose()
        await app.state.neo4j_driver.close()
        await app.state.redis_client.aclose()
        await app.state.embedding_client.aclose()
        await app.state.llm_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="KOS API", version="0.1.0", lifespan=lifespan)
    middleware.install(app)
    app.include_router(health.router)
    app.include_router(sources.router)
    app.include_router(documents.router)
    app.include_router(search.router)
    app.include_router(query.router)
    return app


app = create_app()
