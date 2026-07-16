"""Casos de uso de documentos ingeridos: listado, detalle y chunks (doc 06 §2)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.storage.postgres import chunks_table, documents_table

_DOC_COLUMNS = [
    documents_table.c.doc_id,
    documents_table.c.source_uuid,
    documents_table.c.connector,
    documents_table.c.source_id,
    documents_table.c.title,
    documents_table.c.summary,
    documents_table.c.author,
    documents_table.c.language,
    documents_table.c.keywords,
    documents_table.c.links,
    documents_table.c.confidence,
    documents_table.c.content_hash,
    documents_table.c.created_at,
    documents_table.c.modified_at,
    documents_table.c.fetched_at,
]


async def list_documents(
    engine: AsyncEngine, *, cursor: str | None, limit: int
) -> tuple[list[dict[str, Any]], str | None]:
    """Paginación por cursor opaco (= último doc_id, doc 06 §2)."""
    query = select(*_DOC_COLUMNS).order_by(documents_table.c.doc_id).limit(limit)
    if cursor is not None:
        query = query.where(documents_table.c.doc_id > uuid.UUID(cursor))
    async with engine.connect() as conn:
        rows = [dict(row) for row in (await conn.execute(query)).mappings().all()]
    next_cursor = str(rows[-1]["doc_id"]) if len(rows) == limit else None
    return rows, next_cursor


async def get_document(engine: AsyncEngine, doc_id: uuid.UUID) -> dict[str, Any] | None:
    query = select(*_DOC_COLUMNS, documents_table.c.source_metadata).where(
        documents_table.c.doc_id == doc_id
    )
    async with engine.connect() as conn:
        row = (await conn.execute(query)).mappings().first()
        return dict(row) if row else None


async def list_chunks(
    engine: AsyncEngine, doc_id: uuid.UUID, *, cursor: int | None, limit: int
) -> tuple[list[dict[str, Any]], int | None]:
    """Chunks de un documento en orden; el cursor es la última `position` vista."""
    query = (
        select(
            chunks_table.c.chunk_id,
            chunks_table.c.doc_id,
            chunks_table.c.text,
            chunks_table.c.position,
            chunks_table.c.start_offset,
            chunks_table.c.end_offset,
            chunks_table.c.metadata,
            chunks_table.c.embedding.is_not(None).label("has_embedding"),
        )
        .where(chunks_table.c.doc_id == doc_id)
        .order_by(chunks_table.c.position)
        .limit(limit)
    )
    if cursor is not None:
        query = query.where(chunks_table.c.position > cursor)
    async with engine.connect() as conn:
        rows = [dict(row) for row in (await conn.execute(query)).mappings().all()]
    next_cursor = int(rows[-1]["position"]) if len(rows) == limit else None
    return rows, next_cursor
