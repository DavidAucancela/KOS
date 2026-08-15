"""Herramientas de lectura del grafo: `graph.get_node`, `graph.find_path`,
`graph.query` (doc 06 §4, Fase 2). Mismo mapeo que `GET /v1/graph/*`
(`apps/api/.../routes/graph.py`) vía `kos_core.schemas.graph` (Sprint 16).

Cada tool es un wrapper delgado sobre un `_xxx_core(driver, ...)` testeable
con un driver fake (mismo patrón que `_sync_graph`/`_learn_core` en
`apps/workers`), sin pasar por el protocolo MCP para los tests unitarios."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from kos_core.schemas.graph import (
    GraphNode,
    GraphPathOut,
    GraphQueryRequest,
    GraphQueryResponse,
    GraphQueryTemplate,
    GraphRelation,
    NodeWithNeighborhood,
    neighbor_from_record,
)
from kos_core.storage import neo4j as neo4j_storage


async def _get_node_core(driver: Any, node_id: str) -> NodeWithNeighborhood:
    node = await neo4j_storage.get_node(driver, node_id)
    if node is None:
        raise ValueError(f"Nodo no encontrado: {node_id}")
    neighbors = await neo4j_storage.get_neighborhood(driver, node_id)
    return NodeWithNeighborhood(
        node=GraphNode.model_validate(node),
        neighbors=[neighbor_from_record(n, node_id) for n in neighbors],
    )


async def _find_path_core(driver: Any, from_id: str, to_id: str, max_hops: int) -> GraphPathOut:
    result = await neo4j_storage.find_path(driver, from_id, to_id, max_hops=max_hops)
    if result is None:
        raise ValueError(f"No hay camino entre {from_id} y {to_id}")
    nodes, relations = result
    return GraphPathOut(
        nodes=[GraphNode.model_validate(n) for n in nodes],
        relations=[GraphRelation.model_validate(r) for r in relations],
    )


async def _query_core(driver: Any, request: GraphQueryRequest) -> GraphQueryResponse:
    """Plantillas seguras de consulta (doc 06 §2 `POST /v1/graph/query`): nada
    de Cypher libre, solo `nodes_by_type`/`neighbors_by_type`/`most_connected`/
    `subgraph`."""
    if request.template == "nodes_by_type":
        if request.node_type is None:
            raise ValueError("node_type es requerido para nodes_by_type")
        items, next_cursor = await neo4j_storage.list_nodes_by_type(
            driver, request.node_type, cursor=request.cursor, limit=request.limit
        )
        return GraphQueryResponse(
            template=request.template,
            nodes=[GraphNode.model_validate(n) for n in items],
            next_cursor=next_cursor,
        )

    if request.template == "neighbors_by_type":
        if request.node_id is None:
            raise ValueError("node_id es requerido para neighbors_by_type")
        neighbors = await neo4j_storage.get_neighborhood(
            driver, request.node_id, limit=request.limit
        )
        return GraphQueryResponse(
            template=request.template,
            neighbors=[neighbor_from_record(n, request.node_id) for n in neighbors],
        )

    if request.template == "subgraph":
        nodes = await neo4j_storage.most_connected_nodes(
            driver, node_type=request.node_type, limit=request.limit
        )
        node_ids = [str(node["id"]) for node in nodes]
        relations = await neo4j_storage.subgraph_relations(driver, node_ids)
        return GraphQueryResponse(
            template=request.template,
            nodes=[GraphNode.model_validate(n) for n in nodes],
            relations=[GraphRelation.model_validate(r) for r in relations],
        )

    items = await neo4j_storage.most_connected_nodes(
        driver, node_type=request.node_type, limit=request.limit
    )
    return GraphQueryResponse(
        template=request.template, nodes=[GraphNode.model_validate(n) for n in items]
    )


def register(server: MCPServer) -> None:
    @server.tool(name="graph.get_node")
    async def graph_get_node(ctx: Context, node_id: str) -> NodeWithNeighborhood:
        """Nodo del grafo con su vecindario inmediato (doc 06 §2 `GET /v1/graph/nodes/{id}`)."""
        driver = ctx.request_context.lifespan_context.neo4j_driver
        return await _get_node_core(driver, node_id)

    @server.tool(name="graph.find_path")
    async def graph_find_path(
        ctx: Context, from_id: str, to_id: str, max_hops: int = 4
    ) -> GraphPathOut:
        """Camino más corto entre dos nodos (doc 06 §2 `GET /v1/graph/path`)."""
        driver = ctx.request_context.lifespan_context.neo4j_driver
        return await _find_path_core(driver, from_id, to_id, max_hops)

    @server.tool(name="graph.query")
    async def graph_query(
        ctx: Context,
        template: GraphQueryTemplate,
        node_type: str | None = None,
        node_id: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> GraphQueryResponse:
        """Plantillas seguras de consulta (doc 06 §2 `POST /v1/graph/query`):
        nada de Cypher libre desde el input, solo estas funciones ya validadas."""
        driver = ctx.request_context.lifespan_context.neo4j_driver
        request = GraphQueryRequest(
            template=template, node_type=node_type, node_id=node_id, cursor=cursor, limit=limit
        )
        return await _query_core(driver, request)
