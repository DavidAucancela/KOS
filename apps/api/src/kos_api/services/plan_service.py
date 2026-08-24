"""Casos de uso de auditoría de planes: `GET /v1/plans/{id}` (doc 06 línea 59,
doc 03 §3 regla 3, Sprint 19), y desde el addendum 2026-08-21 también
`GET /v1/plans` (lista reciente) y `GET /v1/plans/metrics` (agregados en el
tiempo, ver `docs/deuda-tecnica.md` "Monitoreo")."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.storage import postgres as postgres_storage


async def get_plan(engine: AsyncEngine, plan_id: uuid.UUID) -> dict[str, Any] | None:
    return await postgres_storage.get_plan(engine, plan_id)


async def list_plans(
    engine: AsyncEngine, *, cursor: str | None, limit: int, degraded_only: bool
) -> tuple[list[dict[str, Any]], str | None]:
    cursor_dt = datetime.fromisoformat(cursor) if cursor is not None else None
    items, next_cursor = await postgres_storage.list_plans(
        engine, cursor=cursor_dt, limit=limit, degraded_only=degraded_only
    )
    return items, next_cursor.isoformat() if next_cursor is not None else None


async def get_plan_metrics(
    engine: AsyncEngine, *, since: datetime, bucket: Literal["hour", "day"]
) -> dict[str, Any]:
    return await postgres_storage.plan_metrics(engine, since=since, bucket=bucket)
