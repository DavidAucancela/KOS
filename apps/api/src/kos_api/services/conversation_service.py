"""Casos de uso de historial de chat: listar, ver detalle, archivar (doc 06 §2
addendum 2026-08-21). La creación de conversaciones y mensajes ocurre dentro de
`routes/query.py` — no hay `POST /v1/conversations` explícito, ver esa ruta."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.storage import postgres as postgres_storage


async def list_conversations(
    engine: AsyncEngine, *, cursor: str | None, limit: int
) -> tuple[list[dict[str, Any]], str | None]:
    cursor_dt = datetime.fromisoformat(cursor) if cursor is not None else None
    items, next_cursor = await postgres_storage.list_conversations(
        engine, cursor=cursor_dt, limit=limit
    )
    return items, next_cursor.isoformat() if next_cursor is not None else None


async def get_conversation(
    engine: AsyncEngine, conversation_id: uuid.UUID
) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    conversation = await postgres_storage.get_conversation(engine, conversation_id)
    if conversation is None:
        return None
    messages = await postgres_storage.list_messages(engine, conversation_id)
    return conversation, messages


async def archive_conversation(engine: AsyncEngine, conversation_id: uuid.UUID) -> bool:
    return await postgres_storage.archive_conversation(engine, conversation_id)
