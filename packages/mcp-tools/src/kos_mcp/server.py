"""Registro y arranque del servidor MCP de KOS (doc 10 §8, ADR-0005).

Transporte stdio (ADR-0006 local-first: un solo usuario, sin infra de auth/red
que justifique SSE/HTTP todavía) — lo spawnea el cliente MCP (Claude
Desktop/Code, un IDE), no un daemon local (por eso no está en `make dev`).

Ciclo de vida: mismo patrón que el `lifespan` de `apps/api/src/kos_api/main.py`
(engine/driver construidos una vez al arrancar, liberados al apagar) y no el de
`apps/workers` (crear/cerrar por tarea) — un servidor MCP stdio vive toda la
sesión del cliente, no se invoca en ráfagas cortas como una task de Celery.

`create_server()` acepta un `AppContext` externo (Sprint 17): `apps/api` lo usa
para embeber este servidor en su propio proceso, compartiendo el mismo
`postgres_engine`/`neo4j_driver`/`embedding_client` que ya construyó su propio
lifespan — evita un segundo pool de conexiones solo para que los agentes
llamen herramientas. Sin `app_context`, el servidor sigue siendo standalone
(entrypoint `python -m kos_mcp.server`, dueño de su propio ciclo de vida)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer
from neo4j import AsyncDriver
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.config import Settings, get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.observability import configure_logging
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_mcp.tools import docs as docs_tools
from kos_mcp.tools import github as github_tools
from kos_mcp.tools import graph as graph_tools
from kos_mcp.tools import memory as memory_tools
from kos_mcp.tools import vector as vector_tools
from kos_mcp.tools import web as web_tools


@dataclass
class AppContext:
    settings: Settings
    postgres_engine: AsyncEngine
    neo4j_driver: AsyncDriver
    embedding_client: OllamaEmbeddingClient


@asynccontextmanager
async def _standalone_lifespan(server: MCPServer) -> AsyncIterator[AppContext]:
    """Ciclo de vida por defecto: el servidor es dueño de sus propias
    conexiones (proceso `python -m kos_mcp.server` real, o tests standalone)."""
    settings = get_settings()
    configure_logging(level=settings.kos_log_level)
    postgres_engine = postgres_storage.create_engine(settings)
    neo4j_driver = neo4j_storage.create_driver(settings)
    embedding_client = OllamaEmbeddingClient(settings)
    try:
        yield AppContext(
            settings=settings,
            postgres_engine=postgres_engine,
            neo4j_driver=neo4j_driver,
            embedding_client=embedding_client,
        )
    finally:
        await postgres_engine.dispose()
        await neo4j_driver.close()
        await embedding_client.aclose()


def create_server(app_context: AppContext | None = None) -> MCPServer:
    if app_context is not None:
        # Ciclo de vida embebido: las conexiones ya existen y las cierra quien
        # las creó (`apps/api`) — este servidor solo las toma prestadas, nunca
        # las dispone.
        @asynccontextmanager
        async def embedded_lifespan(server: MCPServer) -> AsyncIterator[AppContext]:
            yield app_context

        server_lifespan = embedded_lifespan
    else:
        server_lifespan = _standalone_lifespan

    server = MCPServer("kos-mcp-tools", version="0.1.0", lifespan=server_lifespan)
    graph_tools.register(server)
    vector_tools.register(server)
    docs_tools.register(server)
    memory_tools.register(server)
    github_tools.register(server)
    web_tools.register(server)
    return server


mcp = create_server()


if __name__ == "__main__":
    mcp.run(transport="stdio")
