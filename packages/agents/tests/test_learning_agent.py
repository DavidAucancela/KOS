"""Tests unitarios de `LearningAgent` (Sprint 21): `MemoryAgent` fake, sin MCP
ni infra real."""

from __future__ import annotations

from kos_agents.learning import LearningAgent
from kos_core.schemas.agents import AgentRequest, AgentResponse, Constraints


class _FakeMemoryAgent:
    def __init__(self) -> None:
        self.calls: list[AgentRequest] = []

    async def __call__(self, request: AgentRequest) -> AgentResponse:
        self.calls.append(request)
        return AgentResponse(outputs={"approved": True}, confidence=1.0, trace_id=request.trace_id)


async def test_learning_agent_fuerza_confirm_true() -> None:
    memory_agent = _FakeMemoryAgent()
    agent = LearningAgent(memory_agent)

    await agent(
        AgentRequest(
            task="aprender",
            inputs={
                "query": "¿qué es FastAPI?",
                "answer": "un framework web",
                "sources": ["doc-a"],
                "confidence": 0.9,
                "confirm": False,  # el caller nunca debería poder desactivarlo
            },
            constraints=Constraints(),
            trace_id="trace-1",
        )
    )

    assert len(memory_agent.calls) == 1
    forwarded = memory_agent.calls[0]
    assert forwarded.inputs["operation"] == "store"
    assert forwarded.inputs["confirm"] is True
    assert forwarded.inputs["query"] == "¿qué es FastAPI?"


async def test_learning_agent_propaga_la_respuesta_del_memory_agent() -> None:
    memory_agent = _FakeMemoryAgent()
    agent = LearningAgent(memory_agent)

    response = await agent(
        AgentRequest(
            task="aprender",
            inputs={"query": "q", "answer": "a", "sources": [], "confidence": 0.5},
            constraints=Constraints(),
            trace_id="trace-1",
        )
    )

    assert response.outputs["approved"] is True
