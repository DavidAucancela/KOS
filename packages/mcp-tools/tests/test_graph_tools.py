"""Tests unitarios de `kos_mcp.tools.graph` (Sprint 16): storage mockeado, sin
Neo4j real — mismo estilo que `apps/workers/tests/test_graph_sync_task.py`."""

from __future__ import annotations

from typing import Any

import pytest

from kos_core.schemas.graph import GraphQueryRequest
from kos_core.storage import neo4j as neo4j_module
from kos_mcp.tools import graph as graph_tools

_NODE = {
    "id": "node-1",
    "node_type": "Technology",
    "canonical_name": "fastapi",
    "name": "FastAPI",
    "aliases": [],
    "confidence": 0.9,
    "sources": ["doc-a"],
    "extracted_by": "parser@v1",
    "locked": False,
    "created_at": None,
    "updated_at": None,
}

_NEIGHBOR_RECORD = {
    "direction": "outgoing",
    "rel_id": "rel-1",
    "relation_type": "USES",
    "rel_confidence": 0.8,
    "rel_sources": ["doc-a"],
    "rel_extracted_by": "parser@v1",
    "rel_extracted_at": None,
    "rel_rejected": False,
    "neighbor_id": "node-2",
    "neighbor_type": "Technology",
    "neighbor_canonical_name": "docker",
    "neighbor_name": "Docker",
    "neighbor_aliases": [],
    "neighbor_confidence": 0.7,
    "neighbor_sources": ["doc-a"],
    "neighbor_extracted_by": "parser@v1",
    "neighbor_locked": False,
}


async def test_get_node_core_devuelve_nodo_con_vecindario(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_node(driver: Any, node_id: str) -> dict[str, Any]:
        assert node_id == "node-1"
        return _NODE

    async def fake_get_neighborhood(driver: Any, node_id: str, **kwargs: Any) -> list[dict]:
        return [_NEIGHBOR_RECORD]

    monkeypatch.setattr(neo4j_module, "get_node", fake_get_node)
    monkeypatch.setattr(neo4j_module, "get_neighborhood", fake_get_neighborhood)

    result = await graph_tools._get_node_core(None, "node-1")

    assert result.node.canonical_name == "fastapi"
    assert len(result.neighbors) == 1
    assert result.neighbors[0].node.canonical_name == "docker"
    assert result.neighbors[0].direction == "outgoing"


async def test_get_node_core_lanza_si_no_existe(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_node(driver: Any, node_id: str) -> None:
        return None

    monkeypatch.setattr(neo4j_module, "get_node", fake_get_node)

    with pytest.raises(ValueError, match="no-existe"):
        await graph_tools._get_node_core(None, "no-existe")


async def test_find_path_core_lanza_si_no_hay_camino(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_find_path(driver: Any, from_id: str, to_id: str, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(neo4j_module, "find_path", fake_find_path)

    with pytest.raises(ValueError, match="No hay camino"):
        await graph_tools._find_path_core(None, "a", "b", 4)


async def test_query_core_nodes_by_type_requiere_node_type() -> None:
    request = GraphQueryRequest(template="nodes_by_type")
    with pytest.raises(ValueError, match="node_type"):
        await graph_tools._query_core(None, request)


async def test_query_core_most_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_most_connected(driver: Any, **kwargs: Any) -> list[dict]:
        return [_NODE]

    monkeypatch.setattr(neo4j_module, "most_connected_nodes", fake_most_connected)

    request = GraphQueryRequest(template="most_connected", limit=5)
    result = await graph_tools._query_core(None, request)

    assert result.template == "most_connected"
    assert result.nodes is not None
    assert result.nodes[0].canonical_name == "fastapi"
