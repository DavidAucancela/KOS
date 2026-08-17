"""RecommenderAgent (doc 03 §2, doc 11 §5, Sprint 22): persiste recomendaciones
vía la herramienta MCP `recommendations.store`.

No entra al catálogo del Planner ni a `Plan.steps`/`Plan.post` — no resuelve
consultas del usuario, se invoca directo desde `kos.recommend_from_graph_update`
(mismo patrón que `LearningAgent`, Sprint 21). Esqueleto en Sprint 22: no
decide qué recomendar (eso llega en Sprint 23/24) — solo persiste lo que el
llamador ya armó, forzando `confirm=True` por su cuenta (el sistema
completando un paso ya decidido de antemano, no un LLM autónomo — mismo
espíritu que `LearningAgent`/`memory.store`, doc 11 §5)."""

from __future__ import annotations

import time
import uuid

from kos_agents.base import ToolCaller
from kos_core.schemas.agents import AgentRequest, AgentResponse, Cost, EvidenceRef


def _target_evidence(target_entities: list[str]) -> list[EvidenceRef]:
    evidence = []
    for node_id in target_entities:
        try:
            evidence.append(EvidenceRef(node_id=uuid.UUID(node_id)))
        except ValueError:
            continue  # target_entities no-UUID (defensivo): se omite, no rompe la respuesta
    return evidence


class RecommenderAgent:
    def __init__(self, tool_caller: ToolCaller) -> None:
        self._tool_caller = tool_caller

    async def __call__(self, request: AgentRequest) -> AgentResponse:
        started = time.perf_counter()
        target_entities = list(request.inputs.get("target_entities", []))
        arguments = {
            "type": request.inputs["type"],
            "title": request.inputs["title"],
            "description": request.inputs.get("description", ""),
            "evidence": request.inputs.get("evidence", []),
            "target_entities": target_entities,
            "confidence": request.inputs.get("confidence", 0.0),
            "priority": request.inputs.get("priority", 0),
            "source_event_id": request.inputs.get("source_event_id"),
            "confirm": True,
            "trace_id": request.trace_id,
        }
        result = await self._tool_caller.call_tool("recommendations.store", arguments)
        confidence = 1.0 if result.get("approved") else 0.0
        outputs = {
            "approved": result.get("approved"),
            "recommendation_id": result.get("recommendation_id"),
        }
        elapsed_ms = (time.perf_counter() - started) * 1000
        return AgentResponse(
            outputs=outputs,
            evidence=_target_evidence(target_entities) if result.get("approved") else [],
            confidence=confidence,
            cost=Cost(ms=elapsed_ms),
            trace_id=request.trace_id,
        )
