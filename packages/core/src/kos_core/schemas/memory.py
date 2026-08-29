"""Esquema de memoria (doc 04, Fase 3): lo que el sistema aprende, no lo que el
usuario escribió. `storage/postgres.py` (`memory_items`) devuelve dicts; este
modelo es la forma en que cruzan la frontera hacia `apps/api` (regla CLAUDE.md:
nada de dicts sueltos entre paquetes)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from kos_core.confidence import PRUNE_THRESHOLD

MemoryType = Literal["episodic", "semantic", "procedural", "temporal", "preference"]


class SourceRef(BaseModel):
    """Fuente de una memoria con su confidence individual (doc 04 §5, decidido
    2026-08-13): habilita recalcular `confidence` al perder una fuente, igual
    que `source_confidences[]` en el grafo — acá cabe como objeto porque
    Postgres/JSONB sí admite listas de objetos (Neo4j no)."""

    doc_id: str
    confidence: float


class MemoryItem(BaseModel):
    memory_id: UUID
    type: MemoryType
    content: str
    entities: list[str] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    confidence: float
    salience: float
    created_at: datetime
    last_accessed_at: datetime
    archived_at: datetime | None = None
    superseded_by: UUID | None = None
    locked: bool = False
    """Corrección manual (doc 04 §5): confidence fijada por el usuario, no se
    recalcula al perder una fuente ni se consolida — análogo a `locked` en el
    grafo (doc 02 §4 regla 5)."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def prune_candidate(self) -> bool:
        """Doc 04 §5: confidence bajo el umbral tras perder una fuente."""
        return self.confidence < PRUNE_THRESHOLD


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
