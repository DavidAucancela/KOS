"""Test de protocolo (Sprint 16): cliente MCP conectado in-memory al servidor
real (`kos_mcp.server.mcp`) — prueba que la demo del sprint funciona de
verdad, no solo que las funciones envueltas funcionan por separado. Requiere
`make up`. Corre solo con `-m integration`."""

from __future__ import annotations

import uuid

import pytest
from mcp.client import Client
from sqlalchemy import text as sql_text

from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.schemas.graph import GraphNode, NodeWithNeighborhood, neighbor_from_record
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_mcp.client import EmbeddedToolCaller
from kos_mcp.server import AppContext, create_server, mcp

pytestmark = pytest.mark.integration

_NODE_TYPE = "Technology"


async def _cleanup(driver: object, canonical_names: list[str]) -> None:
    async with driver.session() as session:  # type: ignore[attr-defined]
        await session.run(
            f"MATCH (n:{_NODE_TYPE}) WHERE n.canonical_name IN $names DETACH DELETE n",
            {"names": canonical_names},
        )


async def test_list_tools_expone_las_7_herramientas() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()

    names = {t.name for t in tools.tools}
    assert names == {
        "graph.get_node",
        "graph.find_path",
        "graph.query",
        "vector.search",
        "docs.read_document",
        "memory.recall",
        "memory.store",
    }


async def test_graph_get_node_via_mcp_coincide_con_la_api_directa() -> None:
    """La demo de cierre de Sprint 16: `graph.get_node` vía MCP da el mismo
    resultado que llamar directo a la lógica que usa `GET /v1/graph/nodes/{id}`
    — posible por construcción (Sprint 16 promovió el mapeo compartido)."""
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    canonical = f"test-mcp-server-{uuid.uuid4().hex[:8]}"
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

        async with Client(mcp) as client:
            result = await client.call_tool("graph.get_node", {"node_id": node_id})
        mcp_payload = result.structured_content

        node = await neo4j_storage.get_node(driver, node_id)
        assert node is not None
        neighbors = await neo4j_storage.get_neighborhood(driver, node_id)
        api_shape = NodeWithNeighborhood(
            node=GraphNode.model_validate(node),
            neighbors=[neighbor_from_record(n, node_id) for n in neighbors],
        ).model_dump(mode="json")

        assert mcp_payload == api_shape
    finally:
        await _cleanup(driver, [canonical])
        await driver.close()


async def test_memory_store_via_mcp_pide_aprobacion_sin_confirm() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "memory.store",
            {
                "query": "¿qué es KOS?",
                "answer": "un motor de conocimiento",
                "sources": [],
                "confidence": 0.5,
            },
        )
    assert result.is_error is False
    assert result.structured_content["approved"] is False
    assert result.structured_content["memory_id"] is None


async def test_create_server_con_app_context_reusa_las_conexiones_dadas() -> None:
    """Sprint 17: `apps/api` embebe el servidor pasando su propio engine/driver
    en vez de que el servidor abra los suyos — así los agentes no duplican el
    pool de conexiones. `create_server` no debe disponer lo que no creó."""
    settings = get_settings()
    engine = postgres_storage.create_engine(settings)
    driver = neo4j_storage.create_driver(settings)
    embedder = OllamaEmbeddingClient(settings)
    app_context = AppContext(
        settings=settings, postgres_engine=engine, neo4j_driver=driver, embedding_client=embedder
    )
    embedded_server = create_server(app_context)
    try:
        async with EmbeddedToolCaller(embedded_server) as caller:
            result = await caller.call_tool("memory.recall", {"limit": 1})
            assert "items" in result

        # El engine sigue vivo después de que la sesión MCP se cerró — el
        # servidor embebido no lo dispuso, porque no es el dueño.
        async with engine.connect() as conn:
            await conn.execute(sql_text("SELECT 1"))
    finally:
        await engine.dispose()
        await driver.close()
        await embedder.aclose()
