"""MemoryAgent (doc 03 §2): lee y escribe memoria vía las herramientas MCP
`memory.recall`/`memory.store`.

Construido en Sprint 17, standalone — `recall` no está conectado a
`/v1/query` todavía (doc 04 §3 "Recuperación" nunca se construyó, deuda
registrada en `docs/deuda-tecnica.md`, la cierra el Learning agent de
Sprint 21); `store` sigue viajando por `kos.memory_learn`/Celery desde
`POST /v1/query` (doc 04 §1.1: "la UI nunca espera al aprendizaje"), no por
este agente — este agente queda listo para cuando el Planner orqueste el
post-paso `learning` de verdad."""

from __future__ import annotations

import time
from typing import Any

from kos_agents.base import ToolCaller
from kos_core.schemas.agents import AgentRequest, AgentResponse, Cost, EvidenceRef

_OPERATIONS = ("recall", "store")


def _memory_evidence(item: dict[str, Any]) -> EvidenceRef:
    return EvidenceRef(
        memory_id=item["memory_id"],
        quote=item.get("content"),
        score=item.get("confidence"),
    )


class MemoryAgent:
    def __init__(self, tool_caller: ToolCaller) -> None:
        self._tool_caller = tool_caller

    async def __call__(self, request: AgentRequest) -> AgentResponse:
        started = time.perf_counter()
        operation = request.inputs.get("operation")
        if operation not in _OPERATIONS:
            raise ValueError(
                f"MemoryAgent.inputs['operation'] debe ser uno de {_OPERATIONS}, no {operation!r}"
            )

        evidence: list[EvidenceRef]
        outputs: dict[str, object]
        if operation == "recall":
            recall_arguments: dict[str, Any] = {}
            for key in ("type", "q", "cursor", "limit"):
                if key in request.inputs:
                    recall_arguments[key] = request.inputs[key]
            result = await self._tool_caller.call_tool("memory.recall", recall_arguments)
            items = result.get("items") or []
            evidence = [_memory_evidence(item) for item in items]
            confidence = 1.0 if evidence else 0.0
            outputs = {"memory_count": len(evidence)}
        else:
            store_arguments = {
                "query": request.inputs["query"],
                "answer": request.inputs["answer"],
                "sources": request.inputs.get("sources", []),
                "confidence": request.inputs.get("confidence", 0.5),
                "confirm": request.inputs.get("confirm", False),
                "trace_id": request.trace_id,
            }
            result = await self._tool_caller.call_tool("memory.store", store_arguments)
            evidence = []
            confidence = 1.0 if result.get("approved") else 0.0
            outputs = {"approved": result.get("approved"), "memory_id": result.get("memory_id")}

        elapsed_ms = (time.perf_counter() - started) * 1000
        return AgentResponse(
            outputs=outputs,
            evidence=evidence,
            confidence=confidence,
            cost=Cost(ms=elapsed_ms),
            trace_id=request.trace_id,
        )
