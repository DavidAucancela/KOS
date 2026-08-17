"""/v1/graph — lectura y corrección manual del grafo de conocimiento
(doc 06 §2 Grafo, Sprint 9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from neo4j import AsyncDriver
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from kos_api.deps import neo4j_driver, redis_client, settings_dep
from kos_api.services import graph_service
from kos_core.config import Settings
from kos_core.schemas.events import GraphUpdated
from kos_core.schemas.graph import (
    GraphNode,
    GraphPathOut,
    GraphQueryRequest,
    GraphQueryResponse,
    GraphRelation,
    NodeWithNeighborhood,
    neighbor_from_record,
)
from kos_core.storage.redis import publish_event

router = APIRouter(prefix="/v1/graph", tags=["graph"])


class NodesPage(BaseModel):
    items: list[GraphNode]
    next_cursor: str | None


class PatchNodeRequest(BaseModel):
    canonical_name: str | None = None
    node_type: str | None = None
    aliases: list[str] | None = None


class PatchRelationRequest(BaseModel):
    relation_type: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


# Promovido a `kos_core.schemas.graph.neighbor_from_record` en Sprint 16, para
# que esta ruta y la herramienta MCP `graph.get_node` compartan el mismo mapeo.
_neighbor_out = neighbor_from_record


@router.get("/nodes/{node_id}", response_model=NodeWithNeighborhood)
async def get_node(
    node_id: str, driver: AsyncDriver = Depends(neo4j_driver)
) -> NodeWithNeighborhood:
    result = await graph_service.get_node_with_neighborhood(driver, node_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Nodo no encontrado")
    node, neighbors = result
    return NodeWithNeighborhood(
        node=GraphNode.model_validate(node),
        neighbors=[_neighbor_out(n, node_id) for n in neighbors],
    )


@router.get("/path", response_model=GraphPathOut)
async def get_path(
    from_id: str,
    to_id: str,
    max_hops: int = Query(default=4, ge=1, le=6),
    driver: AsyncDriver = Depends(neo4j_driver),
) -> GraphPathOut:
    result = await graph_service.find_path(driver, from_id, to_id, max_hops=max_hops)
    if result is None:
        raise HTTPException(status_code=404, detail="No hay camino entre esos nodos")
    nodes, relations = result
    return GraphPathOut(
        nodes=[GraphNode.model_validate(n) for n in nodes],
        relations=[GraphRelation.model_validate(r) for r in relations],
    )


@router.post("/query", response_model=GraphQueryResponse)
async def query(
    body: GraphQueryRequest, driver: AsyncDriver = Depends(neo4j_driver)
) -> GraphQueryResponse:
    if body.template == "nodes_by_type":
        if body.node_type is None:
            raise HTTPException(status_code=422, detail="node_type es requerido para nodes_by_type")
        try:
            items, next_cursor = await graph_service.nodes_by_type(
                driver, body.node_type, cursor=body.cursor, limit=body.limit
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return GraphQueryResponse(
            template=body.template,
            nodes=[GraphNode.model_validate(n) for n in items],
            next_cursor=next_cursor,
        )

    if body.template == "neighbors_by_type":
        if body.node_id is None:
            raise HTTPException(
                status_code=422, detail="node_id es requerido para neighbors_by_type"
            )
        neighbors = await graph_service.neighbors_by_type(driver, body.node_id, limit=body.limit)
        return GraphQueryResponse(
            template=body.template,
            neighbors=[_neighbor_out(n, body.node_id) for n in neighbors],
        )

    if body.template == "subgraph":
        try:
            nodes, relations = await graph_service.subgraph(
                driver, node_type=body.node_type, limit=body.limit
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return GraphQueryResponse(
            template=body.template,
            nodes=[GraphNode.model_validate(n) for n in nodes],
            relations=[GraphRelation.model_validate(r) for r in relations],
        )

    try:
        items = await graph_service.most_connected(
            driver, node_type=body.node_type, limit=body.limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return GraphQueryResponse(
        template=body.template, nodes=[GraphNode.model_validate(n) for n in items]
    )


@router.patch("/nodes/{node_id}", response_model=GraphNode)
async def patch_node(
    node_id: str,
    body: PatchNodeRequest,
    request: Request,
    driver: AsyncDriver = Depends(neo4j_driver),
    redis: Redis = Depends(redis_client),
    settings: Settings = Depends(settings_dep),
) -> GraphNode:
    try:
        updated = await graph_service.correct_node(
            driver,
            node_id,
            canonical_name=body.canonical_name,
            node_type=body.node_type,
            aliases=body.aliases,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Nodo no encontrado")
    trace_id: str | None = getattr(request.state, "trace_id", None)
    await publish_event(redis, GraphUpdated(node_ids=[node_id], trace_id=trace_id))
    graph_service.enqueue_recommend(
        settings, node_ids=[node_id], relation_ids=[], trace_id=trace_id
    )
    return GraphNode.model_validate(updated)


@router.patch("/relations/{relation_id}", response_model=GraphRelation)
async def patch_relation(
    relation_id: str,
    body: PatchRelationRequest,
    request: Request,
    driver: AsyncDriver = Depends(neo4j_driver),
    redis: Redis = Depends(redis_client),
    settings: Settings = Depends(settings_dep),
) -> GraphRelation:
    try:
        updated = await graph_service.correct_relation(
            driver, relation_id, relation_type=body.relation_type, confidence=body.confidence
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Relación no encontrada")
    trace_id: str | None = getattr(request.state, "trace_id", None)
    await publish_event(redis, GraphUpdated(relation_ids=[relation_id], trace_id=trace_id))
    graph_service.enqueue_recommend(
        settings, node_ids=[], relation_ids=[relation_id], trace_id=trace_id
    )
    return GraphRelation.model_validate(updated)


@router.delete("/relations/{relation_id}", status_code=204)
async def delete_relation(
    relation_id: str,
    request: Request,
    driver: AsyncDriver = Depends(neo4j_driver),
    redis: Redis = Depends(redis_client),
    settings: Settings = Depends(settings_dep),
) -> None:
    rejected = await graph_service.reject_relation(driver, relation_id)
    if not rejected:
        raise HTTPException(status_code=404, detail="Relación no encontrada")
    trace_id: str | None = getattr(request.state, "trace_id", None)
    await publish_event(redis, GraphUpdated(relation_ids=[relation_id], trace_id=trace_id))
    graph_service.enqueue_recommend(
        settings, node_ids=[], relation_ids=[relation_id], trace_id=trace_id
    )
