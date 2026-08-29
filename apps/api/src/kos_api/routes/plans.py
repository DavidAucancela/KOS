"""/v1/plans — auditoría de planes ejecutados (doc 06 línea 59, doc 03 §3 regla
3: "el plan completo se persiste con su traza — es la unidad de depuración y de
evaluación de calidad", Sprint 19). Desde el addendum 2026-08-21 (`docs/deuda-
tecnica.md` "Monitoreo") también expone lista reciente y métricas agregadas.

Importante: las rutas `""` y `/metrics` se declaran ANTES de `/{plan_id}` —
`plan_id` es `uuid.UUID`, así que si `/metrics` quedara después, FastAPI
intentaría parsear "metrics" como UUID y devolvería 422 en vez de llegar al
handler correcto."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine
from kos_api.services import plan_service
from kos_core.schemas.plan import PlanStep
from kos_core.schemas.plan_metrics import (
    AgentDistribution,
    AgentLatency,
    DegradationBreakdown,
    Insight,
    LatencyBucket,
    PeriodSummary,
)

router = APIRouter(prefix="/v1/plans", tags=["plans"])


class PlanOut(BaseModel):
    plan_id: uuid.UUID
    query: str
    steps: list[PlanStep]
    post: list[PlanStep]
    degraded: bool
    degraded_reason: str | None
    elapsed_ms: float
    trace_id: str
    created_at: datetime


class PlanSummary(BaseModel):
    """Versión liviana de `PlanOut` para el listado — sin `steps`/`post`."""

    plan_id: uuid.UUID
    query: str
    degraded: bool
    degraded_reason: str | None
    elapsed_ms: float
    trace_id: str
    created_at: datetime


class PlanPage(BaseModel):
    items: list[PlanSummary]
    next_cursor: str | None


class PlanMetricsOut(BaseModel):
    since: datetime
    current_period: PeriodSummary
    previous_period: PeriodSummary | None
    latency: list[LatencyBucket]
    degradation_by_reason: list[DegradationBreakdown]
    agent_distribution: list[AgentDistribution]
    agent_latency: list[AgentLatency]
    insights: list[Insight]


@router.get("", response_model=PlanPage)
async def list_plans(
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    degraded_only: bool = False,
    engine: AsyncEngine = Depends(postgres_engine),
) -> PlanPage:
    items, next_cursor = await plan_service.list_plans(
        engine, cursor=cursor, limit=limit, degraded_only=degraded_only
    )
    return PlanPage(
        items=[PlanSummary.model_validate(item) for item in items], next_cursor=next_cursor
    )


@router.get("/metrics", response_model=PlanMetricsOut)
async def get_plan_metrics(
    since_hours: int = Query(default=24, ge=1, le=24 * 30),
    bucket: Literal["hour", "day"] = "hour",
    engine: AsyncEngine = Depends(postgres_engine),
) -> PlanMetricsOut:
    since = datetime.now(UTC) - timedelta(hours=since_hours)
    result = await plan_service.get_plan_metrics(engine, since=since, bucket=bucket)
    return PlanMetricsOut.model_validate(result)


@router.get("/{plan_id}", response_model=PlanOut)
async def get_plan(plan_id: uuid.UUID, engine: AsyncEngine = Depends(postgres_engine)) -> PlanOut:
    plan = await plan_service.get_plan(engine, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return PlanOut.model_validate(plan)
