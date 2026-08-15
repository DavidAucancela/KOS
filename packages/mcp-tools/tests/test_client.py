"""Tests unitarios de `kos_mcp.client.EmbeddedToolCaller` (Sprint 17): servidor
MCP mínimo de prueba, sin infra real — solo la lógica de mapeo de resultados/
errores."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from kos_mcp.client import EmbeddedToolCaller, ToolError


def _test_server() -> MCPServer:
    server = MCPServer("test-server")

    @server.tool(name="echo")
    async def echo(value: str) -> dict[str, str]:
        return {"value": value}

    @server.tool(name="boom")
    async def boom() -> dict[str, str]:
        raise ValueError("algo salió mal")

    return server


async def test_call_tool_devuelve_structured_content() -> None:
    async with EmbeddedToolCaller(_test_server()) as caller:
        result = await caller.call_tool("echo", {"value": "hola"})

    assert result == {"value": "hola"}


async def test_call_tool_lanza_tool_error_si_la_tool_falla() -> None:
    async with EmbeddedToolCaller(_test_server()) as caller:
        try:
            await caller.call_tool("boom", {})
            raise AssertionError("debía lanzar ToolError")
        except ToolError as exc:
            assert "boom" in str(exc)
            assert "algo salió mal" in str(exc)


async def test_call_tool_sin_abrir_lanza_runtime_error() -> None:
    caller = EmbeddedToolCaller(_test_server())
    try:
        await caller.call_tool("echo", {"value": "x"})
        raise AssertionError("debía lanzar RuntimeError")
    except RuntimeError as exc:
        assert "no está abierto" in str(exc)
