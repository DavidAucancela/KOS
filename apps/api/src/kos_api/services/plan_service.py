"""Caso de uso de auditoría de planes: `GET /v1/plans/{id}` (doc 06 línea 59,
doc 03 §3 regla 3, Sprint 19)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.storage import postgres as postgres_storage


async def get_plan(engine: AsyncEngine, plan_id: uuid.UUID) -> dict[str, Any] | None:
    return await postgres_storage.get_plan(engine, plan_id)
