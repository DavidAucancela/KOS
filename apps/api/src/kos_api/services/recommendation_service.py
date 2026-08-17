"""Casos de uso de recomendaciones: listado (doc 06 §2, doc 11 §7, Sprint 23)."""

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
