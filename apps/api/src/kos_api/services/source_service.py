"""Casos de uso de fuentes: listar, registrar y sincronizar (doc 06 §2)."""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

from celery import Celery
from sqlalchemy import insert, select, type_coerce, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.config import Settings
from kos_core.storage.postgres import sources_table

# La API no importa kos_workers: encola por nombre de task (doc 09 §2).
SYNC_TASK_NAME = "kos.sync_source"


@lru_cache(maxsize=4)
def _celery_client(redis_url: str) -> Celery:
    return Celery(broker=redis_url)


async def list_sources(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(
            select(sources_table).order_by(sources_table.c.created_at, sources_table.c.name)
        )
        return [dict(row) for row in result.mappings().all()]


async def get_source(engine: AsyncEngine, source_uuid: uuid.UUID) -> dict[str, Any] | None:
    async with engine.connect() as conn:
        result = await conn.execute(
            select(sources_table).where(sources_table.c.source_uuid == source_uuid)
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def create_source(
    engine: AsyncEngine, *, name: str, connector: str, config: dict[str, Any]
) -> dict[str, Any] | None:
    """Registra una fuente. Devuelve None si el nombre ya existe."""
    source_uuid = uuid.uuid4()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                insert(sources_table).values(
                    source_uuid=source_uuid, name=name, connector=connector, config=config
                )
            )
    except IntegrityError:
        return None
    return await get_source(engine, source_uuid)


async def update_source_config(
    engine: AsyncEngine, source_uuid: uuid.UUID, config: dict[str, Any]
) -> dict[str, Any] | None:
    """Shallow-merge de `config` en el JSONB existente (`config || :patch`).
    Clave reconocida: `cloud_safe` (bool) — habilita la síntesis cloud para la
    evidencia de esta fuente (ADR-0007). Devuelve None si la fuente no existe.

    Las claves aceptadas las restringe `SourceConfigPatch` en la ruta
    (`_PATCHABLE_CONFIG_KEYS`): el merge de acá es genérico a propósito, pero el
    endpoint no deja tocar configuración del conector.
    """
    async with engine.begin() as conn:
        result = await conn.execute(
            update(sources_table)
            .where(sources_table.c.source_uuid == source_uuid)
            .values(config=sources_table.c.config.op("||")(type_coerce(config, JSONB)))
            .returning(sources_table.c.source_uuid)
        )
        if result.first() is None:
            return None
    return await get_source(engine, source_uuid)


def enqueue_sync(settings: Settings, source_uuid: uuid.UUID, *, force: bool = False) -> str:
    """Encola la sincronización en los workers y devuelve el job_id de Celery.

    `force=True` es `kos reindex` (doc 05 §5): ignora los content_hash conocidos
    y reencola todo lo descubierto.
    """
    result = _celery_client(settings.redis_url).send_task(
        SYNC_TASK_NAME, args=[str(source_uuid), force], queue="default"
    )
    return str(result.id)
