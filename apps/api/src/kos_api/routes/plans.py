"""GET /v1/plans/{id} — auditoría de un plan ejecutado (doc 06 línea 59,
doc 03 §3 regla 3: "el plan completo se persiste con su traza — es la unidad
de depuración y de evaluación de calidad", Sprint 19)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine
from kos_api.services import plan_service
from kos_core.schemas.plan import PlanStep

router = APIRouter(prefix="/v1/plans", tags=["plans"])


class PlanOut(BaseModel):
    plan_id: uuid.UUID
    query: str
    steps: list[PlanStep]
    degraded: bool
    degraded_reason: str | None
    elapsed_ms: float
    trace_id: str
    created_at: datetime


@router.get("/{plan_id}", response_model=PlanOut)
async def get_plan(plan_id: uuid.UUID, engine: AsyncEngine = Depends(postgres_engine)) -> PlanOut:
    plan = await plan_service.get_plan(engine, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return PlanOut.model_validate(plan)
