"""/v1/sources — registrar fuentes y forzar sincronización (doc 06 §2, Sprint 2)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
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


# Claves que este PATCH puede fusionar en `sources.config`. Es una allowlist a
# propósito: el resto de `config` es configuración del conector (`vault_path`,
# etc.), que se fija al registrar la fuente y no debe poder repuntarse desde el
# endpoint que existe para el interruptor de privacidad de ADR-0007.
_PATCHABLE_CONFIG_KEYS = {"cloud_safe"}


class SourceConfigPatch(BaseModel):
    config: dict[str, Any] = Field(
        examples=[{"cloud_safe": True}],
        description="Claves a fusionar en sources.config. Única aceptada: cloud_safe (bool), "
        "que habilita la síntesis cloud para la evidencia de esta fuente (ADR-0007).",
    )

    @field_validator("config")
    @classmethod
    def _solo_claves_permitidas(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("config vacío: no hay nada que actualizar")
        rechazadas = sorted(set(value) - _PATCHABLE_CONFIG_KEYS)
        if rechazadas:
            permitidas = ", ".join(sorted(_PATCHABLE_CONFIG_KEYS))
            raise ValueError(
                f"claves no permitidas en config: {', '.join(rechazadas)} (solo: {permitidas})"
            )
        if not isinstance(value.get("cloud_safe"), bool):
            raise ValueError("cloud_safe debe ser booleano")
        return value


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


@router.patch("/{source_uuid}", response_model=SourceOut)
async def patch_source(
    source_uuid: uuid.UUID,
    body: SourceConfigPatch,
    engine: AsyncEngine = Depends(postgres_engine),
) -> dict[str, Any]:
    updated = await source_service.update_source_config(engine, source_uuid, body.config)
    if updated is None:
        raise HTTPException(status_code=404, detail="Fuente no registrada")
    return updated


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
