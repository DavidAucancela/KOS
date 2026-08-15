"""Tests unitarios de `RetrievalAgent` (Sprint 17): `ToolCaller` fake, sin MCP
ni infra real."""

from __future__ import annotations

from typing import Any

from kos_agents.retrieval import RetrievalAgent
from kos_core.schemas.agents import AgentRequest, Constraints


class _FakeToolCaller:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        return self.response


async def test_retrieval_agent_llama_vector_search_con_los_inputs() -> None:
    caller = _FakeToolCaller(
        {
            "evidence": [{"doc_id": None, "chunk_id": None, "quote": "FastAPI es un framework"}],
            "confidence": 0.8,
            "degraded": False,
        }
    )
    agent = RetrievalAgent(caller)
    request = AgentRequest(
        task="buscar evidencia para: ¿qué es FastAPI?",
        inputs={"query": "¿qué es FastAPI?", "mode": "hybrid", "limit": 5},
        constraints=Constraints(),
        trace_id="trace-1",
    )

    response = await agent(request)

    assert caller.calls == [
        ("vector.search", {"query": "¿qué es FastAPI?", "limit": 5, "mode": "hybrid"})
    ]
    assert len(response.evidence) == 1
    assert response.confidence == 0.8
    assert response.outputs["hit_count"] == 1
    assert response.outputs["degraded"] is False
    assert response.trace_id == "trace-1"


async def test_retrieval_agent_propaga_degraded() -> None:
    caller = _FakeToolCaller({"evidence": [], "confidence": 0.0, "degraded": True})
    agent = RetrievalAgent(caller)
    request = AgentRequest(
        task="buscar",
        inputs={"query": "x"},
        constraints=Constraints(),
        trace_id="trace-2",
    )

    response = await agent(request)

    assert response.outputs["degraded"] is True
    assert response.evidence == []


async def test_retrieval_agent_usa_defaults_de_limit_y_mode() -> None:
    caller = _FakeToolCaller({"evidence": [], "confidence": 0.0, "degraded": False})
    agent = RetrievalAgent(caller)
    request = AgentRequest(
        task="buscar", inputs={"query": "x"}, constraints=Constraints(), trace_id="t"
    )

    await agent(request)

    [(name, arguments)] = caller.calls
    assert name == "vector.search"
    assert arguments["limit"] == 10
    assert arguments["mode"] == "hybrid"
