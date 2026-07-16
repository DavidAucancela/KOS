"""Candidatos a entidades y relaciones detectados por el parser (doc 02 §2).

Son propuestas: la resolución de entidades (Fase 2) decide qué entra al grafo,
validando `type`/`relation` contra la ontología (doc 02 §3).
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class EntityCandidate(BaseModel):
    name: str
    type: str
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    chunk_ids: list[uuid.UUID] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class RelationCandidate(BaseModel):
    source: str
    relation: str
    target: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    chunk_ids: list[uuid.UUID] = Field(default_factory=list)
