"""RetrievalAgent (doc 03 §2): busca evidencia vía la herramienta MCP
`vector.search`. Sprint 17 lo conecta a `/v1/query` en reemplazo de la lógica
que antes llamaba `kos_core.storage.search` directo desde
`apps/api/.../query_service.py::_retrieve` — ahora el paso de retrieval pasa
por MCP como cualquier otro agente (ADR-0005), sin cambiar el comportamiento
observable (mismo `mode`/degradación/`confidence` que antes, ahora calculados
dentro de la tool)."""

from __future__ import annotations

import time

from kos_agents.base import ToolCaller
from kos_core.schemas.agents import AgentRequest, AgentResponse, Cost


class RetrievalAgent:
    def __init__(self, tool_caller: ToolCaller) -> None:
        self._tool_caller = tool_caller

    async def __call__(self, request: AgentRequest) -> AgentResponse:
        started = time.perf_counter()
        arguments: dict[str, object] = {
            "query": request.inputs["query"],
            "limit": request.inputs.get("limit", 10),
            "mode": request.inputs.get("mode", "hybrid"),
        }
        if "doc_type" in request.inputs:
            arguments["doc_type"] = request.inputs["doc_type"]

        result = await self._tool_caller.call_tool("vector.search", arguments)
        evidence = result.get("evidence") or []

        elapsed_ms = (time.perf_counter() - started) * 1000
        return AgentResponse(
            outputs={"hit_count": len(evidence), "degraded": result.get("degraded", False)},
            evidence=evidence,
            confidence=result.get("confidence", 0.0),
            cost=Cost(ms=elapsed_ms),
            trace_id=request.trace_id,
        )
