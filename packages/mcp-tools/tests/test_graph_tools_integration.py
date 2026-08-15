"""Tests de integración de `kos_mcp.tools.graph` contra Neo4j real (Sprint 16).
Requiere `make up`. Corre solo con `-m integration` — mismo criterio que
`packages/core/tests/test_neo4j_integration.py`."""

from __future__ import annotations

import uuid

import pytest

from kos_core.config import get_settings
from kos_core.schemas.graph import GraphQueryRequest
from kos_core.storage import neo4j as neo4j_storage
from kos_mcp.tools import graph as graph_tools

pytestmark = pytest.mark.integration

_NODE_TYPE = "Technology"


async def _cleanup(driver: object, canonical_names: list[str]) -> None:
    async with driver.session() as session:  # type: ignore[attr-defined]
        await session.run(
            f"MATCH (n:{_NODE_TYPE}) WHERE n.canonical_name IN $names DETACH DELETE n",
            {"names": canonical_names},
        )


async def test_get_node_core_contra_grafo_real() -> None:
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    canonical = f"test-mcp-graph-{uuid.uuid4().hex[:8]}"
    try:
        node_id = await neo4j_storage.merge_node(
            driver,
            node_type=_NODE_TYPE,
            canonical_name=canonical,
            name=canonical,
            aliases=[],
            confidence=0.8,
            sources=["doc-a"],
        )

        result = await graph_tools._get_node_core(driver, node_id)

        assert result.node.canonical_name == canonical
        assert result.neighbors == []
    finally:
        await _cleanup(driver, [canonical])
        await driver.close()


async def test_query_core_most_connected_contra_grafo_real() -> None:
    """El vault real ya tiene miles de nodos: no se puede garantizar que un
    nodo sintético recién creado (0 relaciones) entre en el top acotado a 100
    por `most_connected` — se verifica la forma de la respuesta, no membresía."""
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    request = GraphQueryRequest(template="most_connected", node_type=_NODE_TYPE, limit=5)
    try:
        result = await graph_tools._query_core(driver, request)

        assert result.template == "most_connected"
        assert result.nodes is not None
        assert len(result.nodes) <= 5
        assert all(node.node_type == _NODE_TYPE for node in result.nodes)
    finally:
        await driver.close()
