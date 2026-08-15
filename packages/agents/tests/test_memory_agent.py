"""Tests unitarios de `MemoryAgent` (Sprint 17): `ToolCaller` fake, sin MCP ni
infra real."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from kos_agents.memory import MemoryAgent
from kos_core.schemas.agents import AgentRequest, Constraints


class _FakeToolCaller:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        return self.response


def _request(**inputs: Any) -> AgentRequest:
    return AgentRequest(
        task="operación de memoria", inputs=inputs, constraints=Constraints(), trace_id="trace-1"
    )


async def test_recall_mapea_items_a_evidencia() -> None:
    memory_id = uuid.uuid4()
    caller = _FakeToolCaller(
        {"items": [{"memory_id": str(memory_id), "content": "usa siempre Railway"}]}
    )
    agent = MemoryAgent(caller)

    response = await agent(_request(operation="recall", q="railway", limit=5))

    assert caller.calls == [("memory.recall", {"q": "railway", "limit": 5})]
    assert len(response.evidence) == 1
    assert response.evidence[0].quote == "usa siempre Railway"
    assert response.confidence == 1.0


async def test_store_sin_confirm_da_confidence_cero() -> None:
    caller = _FakeToolCaller({"approved": False, "memory_id": None, "message": "requiere confirm"})
    agent = MemoryAgent(caller)

    response = await agent(
        _request(operation="store", query="¿qué es KOS?", answer="un motor", sources=[])
    )

    [(name, arguments)] = caller.calls
    assert name == "memory.store"
    assert arguments["confirm"] is False
    assert response.outputs["approved"] is False
    assert response.confidence == 0.0


async def test_store_con_confirm_devuelve_memory_id() -> None:
    memory_id = str(uuid.uuid4())
    caller = _FakeToolCaller({"approved": True, "memory_id": memory_id, "message": "ok"})
    agent = MemoryAgent(caller)

    response = await agent(
        _request(operation="store", query="q", answer="a", sources=[], confirm=True, confidence=0.9)
    )

    assert response.outputs["memory_id"] == memory_id
    assert response.confidence == 1.0


async def test_operacion_invalida_lanza_value_error() -> None:
    agent = MemoryAgent(_FakeToolCaller({}))

    with pytest.raises(ValueError, match="operation"):
        await agent(_request(operation="no-existe"))
