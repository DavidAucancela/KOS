"""Contratos base de agentes (doc 03, doc 10 §7 — `base.py`: "Agent (Protocol)
sobre AgentRequest/Response")."""

from __future__ import annotations

from typing import Any, Protocol

from kos_core.schemas.agents import AgentRequest, AgentResponse


class ToolCaller(Protocol):
    """Lo mínimo que un agente necesita para invocar una herramienta MCP —
    duck typing puro: `kos_agents` no importa `packages/mcp-tools` ni el SDK
    `mcp` (doc 09 §2: agentes solo dependen de `core`). La implementación real
    (`kos_mcp.client.EmbeddedToolCaller`) la conecta quien sí puede depender de
    ambos paquetes (`apps/api`) — el agente solo ve esta forma."""

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...


class Agent(Protocol):
    """Un agente es cualquier callable async `AgentRequest -> AgentResponse`
    (doc 06 §3). `task` describe la intención en texto libre; `agent` (el
    campo del `PlanStep` que lo invoca) es la clave de ruteo — no hay un
    vocabulario fijo de `task` por agente (doc 03 §3, ejemplo de plan)."""

    async def __call__(self, request: AgentRequest) -> AgentResponse: ...
