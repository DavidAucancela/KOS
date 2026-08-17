"""/v1/recommendations — lo que el sistema propone sin que se lo pidan
(doc 06 §2, doc 11, Sprint 23)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
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
