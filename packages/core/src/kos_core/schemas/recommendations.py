"""Esquema de recomendaciones (doc 11, Fase 5): lo que el sistema propone sin
que se lo pidan. `storage/postgres.py` (`recommendations`) devuelve dicts;
este modelo es la forma en que cruzan la frontera hacia `apps/api` (regla
CLAUDE.md: nada de dicts sueltos entre paquetes)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from kos_core.schemas.agents import EvidenceRef

RecommendationType = Literal[
    "gap", "contradiction", "related_relation", "roadmap", "reorganization"
]
RecommendationStatus = Literal["pending", "accepted", "dismissed", "expired", "superseded"]


class Recommendation(BaseModel):
    recommendation_id: UUID
    type: RecommendationType
    title: str
    description: str = ""
    evidence: list[EvidenceRef] = Field(default_factory=list)
    target_entities: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    priority: int = 0
    status: RecommendationStatus = "pending"
    dismissed_reason: str | None = None
    source_event_id: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
