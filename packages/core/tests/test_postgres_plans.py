"""Plans contra Postgres real (Sprint 19, doc 03 §3 regla 3, doc 06 línea 59).

Requiere `make up` (Postgres arriba) y la migración 0007 aplicada. Corre solo
con `-m integration`.
"""

from __future__ import annotations

import uuid

import pytest

from datetime import UTC, datetime, timedelta

from kos_core.config import get_settings
from kos_core.schemas.agents import Cost
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
            post=[PlanStep(id="post-learning", agent="learning", task="registrar interacción")],
            degraded=False,
            trace_id="trace-plans-1",
            elapsed_ms=123.4,
        )
        await postgres_storage.insert_plan(engine, plan)

        fetched = await postgres_storage.get_plan(engine, plan_id)
        assert fetched is not None
        assert fetched["query"] == "¿qué es KOS?"
        assert [s["id"] for s in fetched["steps"]] == ["s1", "s2"]
        assert [s["id"] for s in fetched["post"]] == ["post-learning"]
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
        assert fetched["post"] == []
    finally:
        await _cleanup(engine, [plan_id])
        await engine.dispose()


async def test_get_plan_inexistente_devuelve_none() -> None:
    engine = create_engine(get_settings())
    try:
        assert await postgres_storage.get_plan(engine, uuid.uuid4()) is None
    finally:
        await engine.dispose()


async def test_plan_window_agent_latency_promedia_cost_ms_por_agente() -> None:
    """docs/deuda-tecnica.md "Monitoreo": `agent_distribution` ya contaba
    pasos por agente, pero no si `research`/`memory` es sistemáticamente el
    cuello de botella — `_plan_window_agent_latency` agrega el promedio real
    de `cost.ms`. Usa un `created_at` fijo y distintivo + ventana angosta en
    vez de `plan_metrics(since=...)` (que siempre agrega hasta "ahora") para
    no contaminarse con planes reales de otras sesiones en la misma BD."""
    engine = create_engine(get_settings())
    plan_id = uuid.uuid4()
    fixed_created_at = datetime(2031, 1, 1, tzinfo=UTC)
    try:
        plan = Plan(
            plan_id=plan_id,
            query="x",
            steps=[
                PlanStep(id="s1", agent="retrieval", task="buscar", cost=Cost(ms=100.0)),
                PlanStep(id="s2", agent="research", task="buscar afuera", cost=Cost(ms=900.0)),
                # Paso degradado sin `cost` (executor.py degrada sin costo real,
                # ver `_step_inputs`) — no debe contar ni distorsionar el promedio.
                PlanStep(id="s3", agent="graph", task="grafo", cost=None),
            ],
            degraded=False,
            trace_id="trace-plans-metrics",
            elapsed_ms=1000.0,
            created_at=fixed_created_at,
        )
        await postgres_storage.insert_plan(engine, plan)

        async with engine.connect() as conn:
            rows = await postgres_storage._plan_window_agent_latency(
                conn,
                start=fixed_created_at - timedelta(seconds=1),
                end=fixed_created_at + timedelta(seconds=1),
            )

        by_agent = {row["agent"]: row for row in rows}
        assert by_agent["retrieval"]["avg_ms"] == pytest.approx(100.0)
        assert by_agent["retrieval"]["count"] == 1
        assert by_agent["research"]["avg_ms"] == pytest.approx(900.0)
        assert "graph" not in by_agent
    finally:
        await _cleanup(engine, [plan_id])
        await engine.dispose()
