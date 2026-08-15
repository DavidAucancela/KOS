"""/v1/graph — lectura y corrección manual del grafo de conocimiento
(doc 06 §2 Grafo, Sprint 9)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from neo4j import AsyncDriver
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from kos_api.deps import neo4j_driver, redis_client
from kos_api.services import graph_service
from kos_core.schemas.events import GraphUpdated
from kos_core.schemas.graph import GraphNeighbor, GraphNode, GraphRelation
from kos_core.storage.redis import publish_event

router = APIRouter(prefix="/v1/graph", tags=["graph"])


class NodeWithNeighborhood(BaseModel):
    node: GraphNode
    neighbors: list[GraphNeighbor]


class GraphPathOut(BaseModel):
    nodes: list[GraphNode]
    relations: list[GraphRelation]


class NodesPage(BaseModel):
    items: list[GraphNode]
    next_cursor: str | None


GraphQueryTemplate = Literal["nodes_by_type", "neighbors_by_type", "most_connected", "subgraph"]


class GraphQueryRequest(BaseModel):
    template: GraphQueryTemplate
    node_type: str | None = None
    node_id: str | None = None
    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class GraphQueryResponse(BaseModel):
    template: GraphQueryTemplate
    nodes: list[GraphNode] | None = None
    neighbors: list[GraphNeighbor] | None = None
    relations: list[GraphRelation] | None = None
    next_cursor: str | None = None


class PatchNodeRequest(BaseModel):
    canonical_name: str | None = None
    node_type: str | None = None
    aliases: list[str] | None = None


class PatchRelationRequest(BaseModel):
    relation_type: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


def _neighbor_out(record: dict[str, Any], node_id: str) -> GraphNeighbor:
    """`get_neighborhood` no devuelve source_id/target_id de la relación: se
    derivan de la dirección respecto al nodo consultado."""
    direction = record["direction"]
    source_id, target_id = (
        (node_id, record["neighbor_id"])
        if direction == "outgoing"
        else (record["neighbor_id"], node_id)
    )
    return GraphNeighbor(
        relation=GraphRelation(
            id=record["rel_id"],
            relation_type=record["relation_type"],
            source_id=source_id,
            target_id=target_id,
            confidence=record["rel_confidence"],
            sources=record["rel_sources"] or [],
            extracted_by=record["rel_extracted_by"],
            extracted_at=record["rel_extracted_at"],
            rejected=record["rel_rejected"],
        ),
        node=GraphNode(
            id=record["neighbor_id"],
            node_type=record["neighbor_type"],
            canonical_name=record["neighbor_canonical_name"],
            name=record["neighbor_name"],
            aliases=record["neighbor_aliases"] or [],
            confidence=record["neighbor_confidence"],
            sources=record["neighbor_sources"] or [],
            extracted_by=record["neighbor_extracted_by"],
            locked=record["neighbor_locked"],
        ),
        direction=direction,
    )


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
    return GraphNode.model_validate(updated)


@router.patch("/relations/{relation_id}", response_model=GraphRelation)
async def patch_relation(
    relation_id: str,
    body: PatchRelationRequest,
    request: Request,
    driver: AsyncDriver = Depends(neo4j_driver),
    redis: Redis = Depends(redis_client),
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
    return GraphRelation.model_validate(updated)


@router.delete("/relations/{relation_id}", status_code=204)
async def delete_relation(
    relation_id: str,
    request: Request,
    driver: AsyncDriver = Depends(neo4j_driver),
    redis: Redis = Depends(redis_client),
) -> None:
    rejected = await graph_service.reject_relation(driver, relation_id)
    if not rejected:
        raise HTTPException(status_code=404, detail="Relación no encontrada")
    trace_id: str | None = getattr(request.state, "trace_id", None)
    await publish_event(redis, GraphUpdated(relation_ids=[relation_id], trace_id=trace_id))
