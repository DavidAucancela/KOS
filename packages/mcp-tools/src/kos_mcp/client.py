"""Cliente MCP embebido (Sprint 17): expone las herramientas de este mismo
proceso a los agentes (`packages/agents`) sin subproceso — sesión in-memory
contra un `MCPServer` ya construido (`server.create_server(app_context)`),
compartiendo las conexiones de quien lo construyó (`apps/api`).

`kos_agents` no importa este módulo ni el SDK `mcp` (doc 09 §2: agentes solo
dependen de `core`) — recibe cualquier objeto que cumpla
`kos_agents.base.ToolCaller` por duck typing (sin herencia, sin import de
vuelta). Esta clase es la implementación concreta que conecta ambos lados.
"""

from __future__ import annotations

from typing import Any

from mcp.client import Client
from mcp.server.mcpserver import MCPServer


class ToolError(Exception):
    """La herramienta devolvió `is_error=True` — el mensaje trae el detalle
    (ej. `ApprovalRequired` de `memory.store` sin `confirm`, o una excepción
    de la tool)."""


class EmbeddedToolCaller:
    """Sesión MCP in-memory (`mcp.client.Client`) contra un `MCPServer` embebido
    en este mismo proceso. Se abre una vez (`async with`) y se reusa para
    llamadas concurrentes — mismo patrón que `postgres_engine`/`neo4j_driver`
    en `app.state`, no una conexión nueva por request."""

    def __init__(self, server: MCPServer) -> None:
        self._server = server
        self._client: Client | None = None

    async def __aenter__(self) -> EmbeddedToolCaller:
        self._client = Client(self._server)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        if self._client is not None:
            await self._client.__aexit__(*exc_info)
            self._client = None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("EmbeddedToolCaller no está abierto (usar 'async with')")
        result = await self._client.call_tool(name, arguments)
        if result.is_error:
            message = "; ".join(block.text for block in result.content if hasattr(block, "text"))
            raise ToolError(f"{name}: {message}")
        return result.structured_content or {}
