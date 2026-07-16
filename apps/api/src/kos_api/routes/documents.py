"""/v1/documents — documentos ingeridos y sus chunks (doc 06 §2, Sprint 2)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine
from kos_api.services import document_service

router = APIRouter(prefix="/v1/documents", tags=["documents"])


class DocumentSummary(BaseModel):
    doc_id: uuid.UUID
    source_uuid: uuid.UUID | None
    connector: str
    source_id: str
    title: str | None
    summary: str | None
    author: str | None
    language: str | None
    keywords: list[str]
    links: list[str]
    confidence: float
    content_hash: str | None
    created_at: datetime | None
    modified_at: datetime | None
    fetched_at: datetime


class DocumentDetail(DocumentSummary):
    source_metadata: dict[str, Any]


class DocumentPage(BaseModel):
    items: list[DocumentSummary]
    next_cursor: str | None


class ChunkOut(BaseModel):
    chunk_id: uuid.UUID
    doc_id: uuid.UUID
    text: str
    position: int
    start_offset: int | None
    end_offset: int | None
    metadata: dict[str, Any]
    has_embedding: bool


class ChunkPage(BaseModel):
    items: list[ChunkOut]
    next_cursor: int | None


@router.get("", response_model=DocumentPage)
async def list_documents(
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    engine: AsyncEngine = Depends(postgres_engine),
) -> DocumentPage:
    try:
        items, next_cursor = await document_service.list_documents(
            engine, cursor=cursor, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Cursor inválido") from exc
    return DocumentPage(
        items=[DocumentSummary.model_validate(item) for item in items], next_cursor=next_cursor
    )


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(
    doc_id: uuid.UUID, engine: AsyncEngine = Depends(postgres_engine)
) -> DocumentDetail:
    document = await document_service.get_document(engine, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    return DocumentDetail.model_validate(document)


@router.get("/{doc_id}/chunks", response_model=ChunkPage)
async def list_chunks(
    doc_id: uuid.UUID,
    cursor: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    engine: AsyncEngine = Depends(postgres_engine),
) -> ChunkPage:
    document = await document_service.get_document(engine, doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Documento no encontrado")
    items, next_cursor = await document_service.list_chunks(
        engine, doc_id, cursor=cursor, limit=limit
    )
    return ChunkPage(
        items=[ChunkOut.model_validate(item) for item in items], next_cursor=next_cursor
    )
