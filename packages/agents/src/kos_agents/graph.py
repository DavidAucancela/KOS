"""GraphAgent (doc 03 §2): opera el grafo de conocimiento vía las
herramientas MCP `graph.get_node`/`graph.find_path`/`graph.query`.

Construido en Sprint 17, standalone; Sprint 18 lo conecta al `Planner` real
(la decisión de CUÁNDO usar el grafo ya no es una heurística casera, la toma
el LLM al generar el plan)."""

from __future__ import annotations

import time
from typing import Any

from kos_agents.base import ToolCaller
from kos_core.schemas.agents import AgentRequest, AgentResponse, Cost, EvidenceRef

_OPERATIONS = ("get_node", "find_path", "query")


def _node_evidence(node: dict[str, Any]) -> EvidenceRef:
    """`quote` (Sprint 18, bug encontrado probando el Planner contra infra
    real): sin esto, `WritingAgent._build_context` arma una cita vacía para
    cada nodo y el LLM concluye "no hay evidencia" pese a que sí la hay."""
    name = node.get("name") or node.get("canonical_name") or "?"
    node_type = node.get("node_type")
    quote = f"{name} ({node_type})" if node_type else str(name)
    return EvidenceRef(
        node_id=node["id"],
        title=name,
        quote=quote,
        score=node.get("confidence"),
    )


class GraphAgent:
    def __init__(self, tool_caller: ToolCaller) -> None:
        self._tool_caller = tool_caller

    async def __call__(self, request: AgentRequest) -> AgentResponse:
        started = time.perf_counter()
        operation = request.inputs.get("operation")
        if operation not in _OPERATIONS:
            raise ValueError(
                f"GraphAgent.inputs['operation'] debe ser uno de {_OPERATIONS}, no {operation!r}"
            )

        evidence: list[EvidenceRef]
        if operation == "get_node":
            result = await self._tool_caller.call_tool(
                "graph.get_node", {"node_id": request.inputs["node_id"]}
            )
            evidence = [_node_evidence(result["node"])]
            evidence += [_node_evidence(n["node"]) for n in result.get("neighbors") or []]
        elif operation == "find_path":
            path_arguments = {
                "from_id": request.inputs["from_id"],
                "to_id": request.inputs["to_id"],
                "max_hops": request.inputs.get("max_hops", 4),
            }
            result = await self._tool_caller.call_tool("graph.find_path", path_arguments)
            evidence = [_node_evidence(n) for n in result.get("nodes") or []]
        else:
            query_arguments: dict[str, Any] = {"template": request.inputs["template"]}
            for key in ("node_type", "node_id", "cursor", "limit"):
                if key in request.inputs:
                    query_arguments[key] = request.inputs[key]
            result = await self._tool_caller.call_tool("graph.query", query_arguments)
            evidence = [_node_evidence(n) for n in result.get("nodes") or []]

        elapsed_ms = (time.perf_counter() - started) * 1000
        return AgentResponse(
            outputs={"node_count": len(evidence)},
            evidence=evidence,
            confidence=1.0 if evidence else 0.0,
            cost=Cost(ms=elapsed_ms),
            trace_id=request.trace_id,
        )
