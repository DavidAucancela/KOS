"""/v1/recommendations — lo que el sistema propone sin que se lo pidan
(doc 06 §2, doc 11, Sprint 23/25)."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine
from kos_api.services import recommendation_service
from kos_core.schemas.recommendations import (
    Recommendation,
    RecommendationStatus,
    RecommendationType,
)

router = APIRouter(prefix="/v1/recommendations", tags=["recommendations"])


class RecommendationPage(BaseModel):
    items: list[Recommendation]
    next_cursor: str | None


class PatchRecommendationRequest(BaseModel):
    status: Literal["accepted", "dismissed"]
    reason: str | None = None


@router.get("", response_model=RecommendationPage)
async def list_recommendations(
    type: RecommendationType | None = None,
    status: RecommendationStatus | None = None,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    engine: AsyncEngine = Depends(postgres_engine),
) -> RecommendationPage:
    items, next_cursor = await recommendation_service.list_recommendations(
        engine, type=type, status=status, cursor=cursor, limit=limit
    )
    return RecommendationPage(
        items=[Recommendation.model_validate(item) for item in items], next_cursor=next_cursor
    )


@router.patch("/{recommendation_id}", response_model=Recommendation)
async def update_recommendation(
    recommendation_id: uuid.UUID,
    body: PatchRecommendationRequest,
    engine: AsyncEngine = Depends(postgres_engine),
) -> Recommendation:
    """Aceptar/descartar (doc 11 §8): nunca escribe al grafo ni al vault —
    solo cambia el estado de la `Recommendation`. Descartar además evita que
    la misma laguna/contradicción reaparezca en la próxima pasada del
    Recomendador (`has_active_recommendation`, `postgres.py`)."""
    updated = await recommendation_service.update_status(
        engine, recommendation_id, status=body.status, reason=body.reason
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Recomendación no encontrada o ya resuelta")
    return Recommendation.model_validate(updated)
