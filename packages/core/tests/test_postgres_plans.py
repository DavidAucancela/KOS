"""Plans contra Postgres real (Sprint 19, doc 03 §3 regla 3, doc 06 línea 59).

Requiere `make up` (Postgres arriba) y la migración 0007 aplicada. Corre solo
con `-m integration`.
"""

from __future__ import annotations

import uuid

import pytest

from kos_core.config import get_settings
from kos_core.schemas.plan import Plan, PlanStep
from kos_core.storage import postgres as postgres_storage
from kos_core.storage.postgres import create_engine

pytestmark = pytest.mark.integration


async def _cleanup(engine: object, plan_ids: list[uuid.UUID]) -> None:
    from sqlalchemy import delete

    from kos_core.storage.postgres import plans_table

    async with engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.execute(delete(plans_table).where(plans_table.c.plan_id.in_(plan_ids)))


async def test_insert_y_get_plan_round_trip() -> None:
    engine = create_engine(get_settings())
    plan_id = uuid.uuid4()
    try:
        plan = Plan(
            plan_id=plan_id,
            query="¿qué es KOS?",
            steps=[
                PlanStep(id="s1", agent="retrieval", task="buscar", confidence=0.6),
                PlanStep(id="s2", agent="writing", task="redactar", depends_on=["s1"]),
            ],
            degraded=False,
            trace_id="trace-plans-1",
            elapsed_ms=123.4,
        )
        await postgres_storage.insert_plan(engine, plan)

        fetched = await postgres_storage.get_plan(engine, plan_id)
        assert fetched is not None
        assert fetched["query"] == "¿qué es KOS?"
        assert [s["id"] for s in fetched["steps"]] == ["s1", "s2"]
        assert fetched["degraded"] is False
        assert fetched["degraded_reason"] is None
        assert fetched["elapsed_ms"] == pytest.approx(123.4)
        assert fetched["trace_id"] == "trace-plans-1"
    finally:
        await _cleanup(engine, [plan_id])
        await engine.dispose()


async def test_insert_plan_con_degraded_reason() -> None:
    engine = create_engine(get_settings())
    plan_id = uuid.uuid4()
    try:
        plan = Plan(
            plan_id=plan_id,
            query="x",
            steps=[PlanStep(id="s1", agent="retrieval", task="buscar")],
            degraded=True,
            degraded_reason="budget_timeout",
            trace_id="trace-plans-2",
        )
        await postgres_storage.insert_plan(engine, plan)

        fetched = await postgres_storage.get_plan(engine, plan_id)
        assert fetched is not None
        assert fetched["degraded"] is True
        assert fetched["degraded_reason"] == "budget_timeout"
    finally:
        await _cleanup(engine, [plan_id])
        await engine.dispose()


async def test_get_plan_inexistente_devuelve_none() -> None:
    engine = create_engine(get_settings())
    try:
        assert await postgres_storage.get_plan(engine, uuid.uuid4()) is None
    finally:
        await engine.dispose()
