"""Historial de chat persistente (doc 06 §2 addendum 2026-08-21, `docs/deuda-tecnica.md`
"Monitoreo"). Realiza el evento `conversation.completed` que doc 06 §3 ya listaba desde Fase 1
pero nunca se había implementado — `POST /v1/query` era stateless hasta ahora."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from kos_core.schemas.agents import EvidenceRef


class MessageRole(StrEnum):
    user = "user"
    assistant = "assistant"


class Message(BaseModel):
    """Un turno de la conversación. `evidence` se guarda como snapshot completo
    (no una referencia a `plan_id`) para que el historial renderice sin depender
    de que el plan siga siendo consultable — las ramas sintéticas (`/crear-nota`,
    intención de plantilla) no dejan fila en `plans`."""

    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    plan_id: uuid.UUID | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    confidence: float | None = None
    degraded: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Conversation(BaseModel):
    conversation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    title: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    archived_at: datetime | None = None
