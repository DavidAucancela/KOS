"""Esquemas de lectura del grafo de conocimiento (doc 02 §3, doc 06 §2 Grafo).

`storage/neo4j.py` devuelve filas crudas (`NodeRecord`, dicts); estos modelos son
la forma en que ese resultado cruza la frontera hacia `apps/api` (regla CLAUDE.md:
nada de dicts sueltos entre paquetes).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

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
