"""/v1/conversations — historial de chat persistente (doc 06 §2 addendum
2026-08-21, `docs/deuda-tecnica.md` "Monitoreo"). Sin `POST` explícito: una
conversación se crea implícitamente desde `POST /v1/query` cuando no se envía
`conversation_id` — ver esa ruta."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine
from kos_api.services import conversation_service
from kos_core.schemas.agents import EvidenceRef

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])


class ConversationOut(BaseModel):
    conversation_id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    message_id: uuid.UUID
    role: str
    content: str
    plan_id: uuid.UUID | None
    evidence: list[EvidenceRef]
    confidence: float | None
    degraded: bool
    created_at: datetime


class ConversationPage(BaseModel):
    items: list[ConversationOut]
    next_cursor: str | None


class ConversationDetail(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]


@router.get("", response_model=ConversationPage)
async def list_conversations(
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    engine: AsyncEngine = Depends(postgres_engine),
) -> ConversationPage:
    items, next_cursor = await conversation_service.list_conversations(
        engine, cursor=cursor, limit=limit
    )
    return ConversationPage(
        items=[ConversationOut.model_validate(item) for item in items], next_cursor=next_cursor
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID, engine: AsyncEngine = Depends(postgres_engine)
) -> ConversationDetail:
    result = await conversation_service.get_conversation(engine, conversation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    conversation, messages = result
    return ConversationDetail(
        conversation=ConversationOut.model_validate(conversation),
        messages=[MessageOut.model_validate(message) for message in messages],
    )


@router.delete("/{conversation_id}", status_code=204)
async def archive_conversation(
    conversation_id: uuid.UUID, engine: AsyncEngine = Depends(postgres_engine)
) -> None:
    archived = await conversation_service.archive_conversation(engine, conversation_id)
    if not archived:
        raise HTTPException(status_code=404, detail="Conversación no encontrada o ya archivada")
