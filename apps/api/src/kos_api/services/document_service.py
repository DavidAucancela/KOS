"""Casos de uso de documentos ingeridos: listado, detalle y chunks (doc 06 §2)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.storage.postgres import _DOCUMENT_COLUMNS, documents_table
from kos_core.storage.postgres import get_document as get_document
from kos_core.storage.postgres import list_chunks as list_chunks


async def list_documents(
    engine: AsyncEngine, *, cursor: str | None, limit: int
) -> tuple[list[dict[str, Any]], str | None]:
    """Paginación por cursor opaco (= último doc_id, doc 06 §2).

    Los documentos con tombstone (borrados en la fuente, doc 05 §5) quedan
    fuera del listado por defecto; siguen accesibles por `get_document`.
    """
    query = (
        select(*_DOCUMENT_COLUMNS)
        .where(documents_table.c.deleted_at.is_(None))
        .order_by(documents_table.c.doc_id)
        .limit(limit)
    )
    if cursor is not None:
        query = query.where(documents_table.c.doc_id > uuid.UUID(cursor))
    async with engine.connect() as conn:
        rows = [dict(row) for row in (await conn.execute(query)).mappings().all()]
    next_cursor = str(rows[-1]["doc_id"]) if len(rows) == limit else None
    return rows, next_cursor
