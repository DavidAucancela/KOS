"""Casos de uso de memoria: auditoría y encolado de aprendizaje (doc 06 §2,
doc 04 §1.1 — Sprint 12). La API no importa `kos_workers`: encola por nombre
de task (doc 09 §2), mismo patrón que `source_service.enqueue_sync`."""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any

from celery import Celery
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.config import Settings
from kos_core.storage import postgres as postgres_storage

LEARN_TASK_NAME = "kos.memory_learn"


@lru_cache(maxsize=4)
def _celery_client(redis_url: str) -> Celery:
    return Celery(broker=redis_url)


def enqueue_learn(
    settings: Settings, *, query: str, answer: str, sources: list[str], confidence: float
) -> None:
    """Encola `kos.memory_learn` sin esperar el resultado (doc 04 §4: 'la UI
    nunca espera al aprendizaje') — no hay nada que devolverle al caller."""
    _celery_client(settings.redis_url).send_task(
        LEARN_TASK_NAME,
        kwargs={"query": query, "answer": answer, "sources": sources, "confidence": confidence},
        queue="default",
    )


async def list_memories(
    engine: AsyncEngine, *, type: str | None, q: str | None, cursor: str | None, limit: int
) -> tuple[list[dict[str, Any]], str | None]:
    cursor_uuid = uuid.UUID(cursor) if cursor is not None else None
    items, next_cursor = await postgres_storage.list_memories(
        engine, type=type, q=q, cursor=cursor_uuid, limit=limit
    )
    return items, str(next_cursor) if next_cursor is not None else None


async def archive_memory(engine: AsyncEngine, memory_id: uuid.UUID) -> bool:
    return await postgres_storage.archive_memory(engine, memory_id)


async def correct_memory(
    engine: AsyncEngine,
    memory_id: uuid.UUID,
    *,
    content: str | None,
    type: str | None,
    confidence: float | None,
) -> dict[str, Any] | None:
    """Corrección manual (doc 04 §5): fija campos y marca `locked`."""
    return await postgres_storage.correct_memory(
        engine, memory_id, content=content, type=type, confidence=confidence
    )
