"""Herramienta de lectura de documentos: `docs.read_document` (doc 06 §4, Fase 1).
El cuerpo no se persiste crudo en Postgres (vive en MinIO) — se reconstruye
concatenando chunks en orden, mismo mapeo que `GET /v1/documents/{id}/chunks`
(Sprint 16, `kos_core.storage.postgres.get_document`/`list_chunks`)."""

from __future__ import annotations

import uuid
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel

from kos_core.schemas.agents import EvidenceRef
from kos_core.storage import postgres as postgres_storage


class DocumentChunkPage(BaseModel):
    doc_id: uuid.UUID
    title: str | None
    summary: str | None
    connector: str
    source_id: str
    text: str
    evidence: list[EvidenceRef]
    next_cursor: int | None


async def _read_document_core(
    engine: Any, doc_id: str, cursor: int | None, limit: int
) -> DocumentChunkPage:
    doc_uuid = uuid.UUID(doc_id)
    document = await postgres_storage.get_document(engine, doc_uuid)
    if document is None:
        raise ValueError(f"Documento no encontrado: {doc_id}")
    chunks, next_cursor = await postgres_storage.list_chunks(
        engine, doc_uuid, cursor=cursor, limit=limit
    )
    return DocumentChunkPage(
        doc_id=doc_uuid,
        title=document["title"],
        summary=document["summary"],
        connector=document["connector"],
        source_id=document["source_id"],
        text="\n\n".join(chunk["text"] for chunk in chunks),
        evidence=[
            EvidenceRef(
                doc_id=doc_uuid,
                chunk_id=chunk["chunk_id"],
                quote=chunk["text"],
                title=document["title"],
                source_id=document["source_id"],
                connector=document["connector"],
            )
            for chunk in chunks
        ],
        next_cursor=next_cursor,
    )


def register(server: MCPServer) -> None:
    @server.tool(name="docs.read_document")
    async def docs_read_document(
        ctx: Context, doc_id: str, cursor: int | None = None, limit: int = 20
    ) -> DocumentChunkPage:
        """Metadata + texto de un documento, paginado por chunk (doc 06 §2)."""
        engine = ctx.request_context.lifespan_context.postgres_engine
        return await _read_document_core(engine, doc_id, cursor, limit)
