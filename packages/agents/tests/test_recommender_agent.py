"""Tests unitarios de `RecommenderAgent` (Sprint 22, doc 11 §5): `ToolCaller`
fake, sin MCP ni infra real."""

from __future__ import annotations

from typing import Any

from kos_agents.recommender import RecommenderAgent
from kos_core.schemas.agents import AgentRequest


class _FakeToolCaller:
    def __init__(self, result: dict[str, Any]) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._result = result

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        return self._result


async def test_recommender_agent_fuerza_confirm_true() -> None:
    caller = _FakeToolCaller({"approved": True, "recommendation_id": "rec-1"})
    agent = RecommenderAgent(caller)

    await agent(
        AgentRequest(
            task="recomendación esqueleto",
            inputs={
                "type": "gap",
                "title": "Falta KNOWS",
                "description": "desc",
                "target_entities": [],
                "confidence": 0.0,
                "priority": 0,
                "source_event_id": "trace-source",
            },
            trace_id="trace-1",
        )
    )

    [(name, arguments)] = caller.calls
    assert name == "recommendations.store"
    assert arguments["confirm"] is True
    assert arguments["type"] == "gap"
    assert arguments["title"] == "Falta KNOWS"
    assert arguments["source_event_id"] == "trace-source"


async def test_recommender_agent_propaga_recommendation_id() -> None:
    caller = _FakeToolCaller({"approved": True, "recommendation_id": "rec-1"})
    agent = RecommenderAgent(caller)

    response = await agent(
        AgentRequest(
            task="recomendación esqueleto",
            inputs={"type": "gap", "title": "t"},
            trace_id="trace-1",
        )
    )

    assert response.outputs["recommendation_id"] == "rec-1"
    assert response.confidence == 1.0


async def test_recommender_agent_sin_aprobacion_confidence_cero() -> None:
    caller = _FakeToolCaller({"approved": False, "recommendation_id": None})
    agent = RecommenderAgent(caller)

    response = await agent(
        AgentRequest(
            task="recomendación esqueleto",
            inputs={"type": "gap", "title": "t"},
            trace_id="trace-1",
        )
    )

    assert response.confidence == 0.0
    assert response.evidence == []


async def test_recommender_agent_arma_evidence_de_target_entities_uuid() -> None:
    caller = _FakeToolCaller({"approved": True, "recommendation_id": "rec-1"})
    agent = RecommenderAgent(caller)

    response = await agent(
        AgentRequest(
            task="recomendación esqueleto",
            inputs={
                "type": "gap",
                "title": "t",
                "target_entities": [
                    "3fae7c1e-1111-4a2b-8c3d-000000000001",
                    "no-es-un-uuid",
                ],
            },
            trace_id="trace-1",
        )
    )

    assert len(response.evidence) == 1
    assert str(response.evidence[0].node_id) == "3fae7c1e-1111-4a2b-8c3d-000000000001"
