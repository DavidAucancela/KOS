"""Esquema de propuestas de memoria (`docs/deuda-tecnica.md`, mitigación del
riesgo de que el Planner elija `memory.store` sin aprobación humana real):
`storage/postgres.py` (`memory_proposals`) devuelve dicts; este modelo es la
forma en que cruzan la frontera hacia `apps/api` (regla CLAUDE.md: nada de
dicts sueltos entre paquetes)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

MemoryProposalStatus = Literal["pending", "approved", "rejected"]


class MemoryProposal(BaseModel):
    proposal_id: UUID
    query: str
    answer: str
    sources: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: MemoryProposalStatus = "pending"
    rejected_reason: str | None = None
    memory_id: UUID | None = None
    trace_id: str
    created_at: datetime
    resolved_at: datetime | None = None
