"""Contratos del Planner (doc 03 §3/§5, Sprint 18): `PlanRequest` es el tipo que
el diagrama de secuencia de doc 03 §5 nombra (`API->>P: PlanRequest`) pero nunca
se había implementado — hasta Sprint 17 el pipeline era fijo y no necesitaba un
plan real. `PlanStep` se promueve acá desde `apps/api/.../query_service.py`
(donde vivía como el paso fijo retrieval→writing) porque `kos_agents.planner`
también lo necesita para construir planes dinámicos."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from kos_core.schemas.agents import Constraints, Cost


class PlanStep(BaseModel):
    """Un paso del plan; la unidad de traza y depuración (doc 03 §3). `inputs`
    es lo que el Planner le pasa al agente — antes no existía porque el
    pipeline fijo no necesitaba parametrizar nada por paso."""

    id: str
    agent: str
    task: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    evidence_count: int | None = None
    confidence: float | None = None
    cost: Cost | None = None


class PlanRequest(BaseModel):
    """Input al Planner (doc 03 §5). `mode`/`limit` son hints de retrieval que
    el Planner respeta tanto en el plan fijo (fallback) como al construir el
    prompt para el plan dinámico — no son presupuestos (eso es `constraints`),
    son parámetros del dominio de la consulta."""

    query: str
    constraints: Constraints = Field(default_factory=Constraints)
    trace_id: str
    mode: str = "hybrid"
    limit: int = 10


class Plan(BaseModel):
    """Plan generado (dinámico) o degradado (fijo, doc 03 §3 regla 4)."""

    plan_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    query: str
    steps: list[PlanStep]
    degraded: bool = False
    trace_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
