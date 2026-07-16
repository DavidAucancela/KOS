"""Eventos del bus Redis (doc 06 §3).

Todos llevan `event_id` (dedupe), `schema_version`, `occurred_at` y `trace_id`.
Nombres: `dominio.pasado` (doc 09 §3).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(UTC)


class EventBase(BaseModel):
    name: ClassVar[str]

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    schema_version: int = 1
    occurred_at: datetime = Field(default_factory=_now)
    trace_id: str | None = None


class DocumentIngested(EventBase):
    """Emitido por la ingesta al encolar un documento; lo consume el parser."""

    name: ClassVar[str] = "document.ingested"

    doc_id: uuid.UUID
    connector: str
    source_id: str
    content_hash: str


class DocumentParsed(EventBase):
    """Emitido por el parser; lo consumen grafo y aprendizaje."""

    name: ClassVar[str] = "document.parsed"

    doc_id: uuid.UUID
    pipeline_version: str


class DocumentDeleted(EventBase):
    """Emitido por la ingesta al detectar un borrado en la fuente."""

    name: ClassVar[str] = "document.deleted"

    doc_id: uuid.UUID
