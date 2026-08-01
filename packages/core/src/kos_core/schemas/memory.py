"""Esquema de memoria (doc 04, Fase 3): lo que el sistema aprende, no lo que el
usuario escribió. `storage/postgres.py` (`memory_items`) devuelve dicts; este
modelo es la forma en que cruzan la frontera hacia `apps/api` (regla CLAUDE.md:
nada de dicts sueltos entre paquetes)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

MemoryType = Literal["episodic", "semantic", "procedural", "temporal", "preference"]


class MemoryItem(BaseModel):
    memory_id: UUID
    type: MemoryType
    content: str
    entities: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    confidence: float
    salience: float
    created_at: datetime
    last_accessed_at: datetime
    archived_at: datetime | None = None
    superseded_by: UUID | None = None


def effective_salience(
    salience: float,
    last_accessed_at: datetime,
    *,
    half_life_days: float,
    now: datetime | None = None,
) -> float:
    """Decaimiento exponencial de `salience` (doc 04 §3): a cada `half_life_days`
    sin refuerzo (sin que se vuelva a acceder a la memoria), el valor se reduce
    a la mitad. Calculado al leer, no mutado en un job aparte — evita reescribir
    la tabla entera en cada tick solo para bajar un número."""
    now = now or datetime.now(UTC)
    elapsed_days = max((now - last_accessed_at).total_seconds(), 0.0) / 86400.0
    if half_life_days <= 0:
        return salience
    return salience * float(0.5 ** (elapsed_days / half_life_days))
