"""Modelo unificado de documentos (doc 02 §2), común a todos los conectores."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from kos_core.schemas.entities import EntityCandidate, RelationCandidate

# Espacio de nombres fijo para derivar doc_ids estables con uuid5.
KOS_DOC_NAMESPACE = uuid.UUID("6f8a1b2c-9d3e-4f50-8a71-c2b4d6e8f0a1")


def make_doc_id(connector: str, source_id: str) -> uuid.UUID:
    """UUID estable derivado de (connector, source_id) — doc 02 §2."""
    return uuid.uuid5(KOS_DOC_NAMESPACE, f"{connector}:{source_id}")


class RawDocument(BaseModel):
    """Lo que produce un conector, antes de cualquier parseo."""

    source_id: str
    connector: str
    content: str | bytes
    mime_type: str = "text/markdown"
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime
    raw_bytes: bytes | None = None
    """Blob original cuando difiere de `content` (doc 05 §2: binarios como PDF,
    cuyo `content` es el texto ya extraído que consume el pipeline). Si es
    `None`, el blob subido a MinIO es `content` mismo."""


class ChunkPosition(BaseModel):
    """Offset y orden del chunk dentro del documento original."""

    order: int = Field(ge=0)
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class Chunk(BaseModel):
    chunk_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    doc_id: uuid.UUID
    text: str
    position: ChunkPosition
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    """Lo que produce el parser; las entidades/relaciones son candidatas al grafo.

    `body` es el texto completo normalizado: lo siembra el bootstrap del pipeline
    y lo consumen las etapas (chunking, resumen); no se persiste como tal — el
    original vive en MinIO y el texto consultable en los chunks.
    """

    doc_id: uuid.UUID
    title: str
    body: str | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    author: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    language: str | None = None
    chunks: list[Chunk] = Field(default_factory=list)
    entities: list[EntityCandidate] = Field(default_factory=list)
    relations: list[RelationCandidate] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
