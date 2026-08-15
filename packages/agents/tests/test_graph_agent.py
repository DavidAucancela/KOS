"""Tests unitarios de `GraphAgent` (Sprint 17): `ToolCaller` fake, sin MCP ni
infra real."""

from __future__ import annotations

from typing import Any

import pytest

from kos_agents.graph import GraphAgent
from kos_core.schemas.agents import AgentRequest, Constraints

_NODE_ID = "11111111-1111-1111-1111-111111111111"
_NEIGHBOR_ID = "22222222-2222-2222-2222-222222222222"
_NODE = {"id": _NODE_ID, "name": "FastAPI", "canonical_name": "fastapi", "confidence": 0.9}
_NEIGHBOR_NODE = {
    "id": _NEIGHBOR_ID,
    "name": "Docker",
    "canonical_name": "docker",
    "confidence": 0.7,
}


class _FakeToolCaller:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        return self.response


def _request(**inputs: Any) -> AgentRequest:
    return AgentRequest(
        task="operación de grafo", inputs=inputs, constraints=Constraints(), trace_id="trace-1"
    )


async def test_get_node_incluye_el_nodo_y_sus_vecinos() -> None:
    caller = _FakeToolCaller(
        {"node": _NODE, "neighbors": [{"node": _NEIGHBOR_NODE, "direction": "outgoing"}]}
    )
    agent = GraphAgent(caller)

    response = await agent(_request(operation="get_node", node_id=_NODE_ID))

    assert caller.calls == [("graph.get_node", {"node_id": _NODE_ID})]
    assert len(response.evidence) == 2
    assert response.confidence == 1.0


async def test_find_path_mapea_los_nodos_del_camino() -> None:
    caller = _FakeToolCaller({"nodes": [_NODE, _NEIGHBOR_NODE], "relations": []})
    agent = GraphAgent(caller)

    response = await agent(_request(operation="find_path", from_id=_NODE_ID, to_id=_NEIGHBOR_ID))

    assert caller.calls == [
        ("graph.find_path", {"from_id": _NODE_ID, "to_id": _NEIGHBOR_ID, "max_hops": 4})
    ]
    assert len(response.evidence) == 2


async def test_query_sin_resultados_da_confidence_cero() -> None:
    caller = _FakeToolCaller({"template": "most_connected", "nodes": []})
    agent = GraphAgent(caller)

    response = await agent(_request(operation="query", template="most_connected"))

    assert response.evidence == []
    assert response.confidence == 0.0


async def test_operacion_invalida_lanza_value_error() -> None:
    agent = GraphAgent(_FakeToolCaller({}))

    with pytest.raises(ValueError, match="operation"):
        await agent(_request(operation="no-existe"))
