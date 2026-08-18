"""Casos de uso de recomendaciones: listado y aceptar/descartar (doc 06 §2,
doc 11 §7/§8, Sprint 23/25)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.storage import postgres as postgres_storage


async def list_recommendations(
    engine: AsyncEngine, *, type: str | None, status: str | None, cursor: str | None, limit: int
) -> tuple[list[dict[str, Any]], str | None]:
    cursor_uuid = uuid.UUID(cursor) if cursor is not None else None
    items, next_cursor = await postgres_storage.list_recommendations(
        engine, type=type, status=status, cursor=cursor_uuid, limit=limit
    )
    return items, str(next_cursor) if next_cursor is not None else None


async def update_status(
    engine: AsyncEngine, recommendation_id: uuid.UUID, *, status: str, reason: str | None
) -> dict[str, Any] | None:
    return await postgres_storage.update_recommendation_status(
        engine, recommendation_id, status=status, dismissed_reason=reason
    )
