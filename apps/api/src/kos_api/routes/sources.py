"""/v1/sources — registrar fuentes y forzar sincronización (doc 06 §2, Sprint 2)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine, settings_dep
from kos_api.services import source_service
from kos_core.config import Settings

router = APIRouter(prefix="/v1/sources", tags=["sources"])


class SourceIn(BaseModel):
    name: str = Field(min_length=1)
    connector: str = Field(min_length=1, examples=["obsidian"])
    config: dict[str, Any] = Field(default_factory=dict)


class SourceOut(SourceIn):
    source_uuid: uuid.UUID
    enabled: bool
    created_at: datetime


class SyncAccepted(BaseModel):
    job_id: str
    source_uuid: uuid.UUID


@router.get("", response_model=list[SourceOut])
async def list_sources(engine: AsyncEngine = Depends(postgres_engine)) -> list[dict[str, Any]]:
    return await source_service.list_sources(engine)


@router.post("", response_model=SourceOut, status_code=201)
async def create_source(
    body: SourceIn, engine: AsyncEngine = Depends(postgres_engine)
) -> dict[str, Any]:
    created = await source_service.create_source(
        engine, name=body.name, connector=body.connector, config=body.config
    )
    if created is None:
        raise HTTPException(status_code=409, detail=f"Ya existe una fuente llamada {body.name!r}")
    return created


@router.post("/{source_uuid}/sync", response_model=SyncAccepted, status_code=202)
async def sync_source(
    source_uuid: uuid.UUID,
    engine: AsyncEngine = Depends(postgres_engine),
    settings: Settings = Depends(settings_dep),
) -> SyncAccepted:
    source = await source_service.get_source(engine, source_uuid)
    if source is None:
        raise HTTPException(status_code=404, detail="Fuente no registrada")
    if not source["enabled"]:
        raise HTTPException(status_code=409, detail="La fuente está deshabilitada")
    job_id = source_service.enqueue_sync(settings, source_uuid)
    return SyncAccepted(job_id=job_id, source_uuid=source_uuid)
