"""Esquemas de lectura del grafo de conocimiento (doc 02 §3, doc 06 §2 Grafo).

`storage/neo4j.py` devuelve filas crudas (`NodeRecord`, dicts); estos modelos son
la forma en que ese resultado cruza la frontera hacia `apps/api` (regla CLAUDE.md:
nada de dicts sueltos entre paquetes).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

from kos_core.confidence import PRUNE_THRESHOLD
from kos_core.ontology import NodeType, RelationType


class GraphNode(BaseModel):
    id: str
    node_type: NodeType
    canonical_name: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    confidence: float
    sources: list[str] = Field(default_factory=list)
    extracted_by: str
    locked: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def prune_candidate(self) -> bool:
        """Doc 04 §5: confidence bajo el umbral tras perder una fuente."""
        return self.confidence < PRUNE_THRESHOLD


class GraphRelation(BaseModel):
    id: str
    relation_type: RelationType
    source_id: str
    target_id: str
    confidence: float
    sources: list[str] = Field(default_factory=list)
    extracted_by: str
    extracted_at: datetime | None = None
    rejected: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def prune_candidate(self) -> bool:
        """Doc 04 §5: confidence bajo el umbral tras perder una fuente."""
        return self.confidence < PRUNE_THRESHOLD


class GraphNeighbor(BaseModel):
    relation: GraphRelation
    node: GraphNode
    direction: Literal["outgoing", "incoming"]


def neighbor_from_record(record: dict[str, Any], node_id: str) -> GraphNeighbor:
    """`get_neighborhood` no devuelve source_id/target_id de la relación: se
    derivan de la dirección respecto al nodo consultado. Promovido a core en
    Sprint 16 (antes `_neighbor_out` en `apps/api/.../routes/graph.py`) para
    que `GET /v1/graph/nodes/{id}` y la herramienta MCP `graph.get_node`
    compartan el mismo mapeo — no solo se comportan igual, son la misma
    función."""
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


class NodeWithNeighborhood(BaseModel):
    node: GraphNode
    neighbors: list[GraphNeighbor]


class GraphPathOut(BaseModel):
    nodes: list[GraphNode]
    relations: list[GraphRelation]


# Plantillas seguras de POST /v1/graph/query (doc 06 §2): nada de Cypher libre
# desde el body, solo estas funciones ya validadas (`graph_service.py`).
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
