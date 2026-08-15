"""/v1/memory — auditoría de memoria (doc 06 §2, Sprint 12, doc 04)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, computed_field
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine
from kos_api.services import memory_service
from kos_core.confidence import PRUNE_THRESHOLD
from kos_core.schemas.memory import MemoryType, SourceRef

router = APIRouter(prefix="/v1/memory", tags=["memory"])


class MemoryOut(BaseModel):
    memory_id: uuid.UUID
    type: MemoryType
    content: str
    entities: list[str]
    sources: list[SourceRef]
    confidence: float
    salience: float
    created_at: datetime
    last_accessed_at: datetime
    archived_at: datetime | None
    superseded_by: uuid.UUID | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def prune_candidate(self) -> bool:
        """Doc 04 §5: confidence bajo el umbral tras perder una fuente."""
        return self.confidence < PRUNE_THRESHOLD


class MemoryPage(BaseModel):
    items: list[MemoryOut]
    next_cursor: str | None


@router.get("", response_model=MemoryPage)
async def list_memories(
    type: MemoryType | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    engine: AsyncEngine = Depends(postgres_engine),
) -> MemoryPage:
    try:
        items, next_cursor = await memory_service.list_memories(
            engine, type=type, q=q, cursor=cursor, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Cursor inválido") from exc
    return MemoryPage(
        items=[MemoryOut.model_validate(item) for item in items], next_cursor=next_cursor
    )


@router.delete("/{memory_id}", status_code=204)
async def archive_memory(
    memory_id: uuid.UUID, engine: AsyncEngine = Depends(postgres_engine)
) -> None:
    archived = await memory_service.archive_memory(engine, memory_id)
    if not archived:
        raise HTTPException(status_code=404, detail="Memoria no encontrada o ya archivada")
