"""Recomendaciones contra Postgres real (Sprint 22/23, doc 11 §2/§6/§7).

Requiere `make up` (Postgres arriba) y la migración 0009 aplicada. Corre solo
con `-m integration` — mismo motivo que `test_postgres_memory.py`.
"""

from __future__ import annotations

import uuid

import pytest

from kos_core.config import get_settings
from kos_core.storage import postgres as postgres_storage
from kos_core.storage.postgres import create_engine

pytestmark = pytest.mark.integration


async def _cleanup(engine: object, recommendation_ids: list[uuid.UUID]) -> None:
    from sqlalchemy import delete

    from kos_core.storage.postgres import recommendations_table

    async with engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.execute(
            delete(recommendations_table).where(
                recommendations_table.c.recommendation_id.in_(recommendation_ids)
            )
        )


async def _insert(
    engine: object, *, target_entities: list[str], status: str = "pending"
) -> uuid.UUID:
    recommendation_id = uuid.uuid4()
    await postgres_storage.insert_recommendation(
        engine,  # type: ignore[arg-type]
        recommendation_id=recommendation_id,
        type="gap",
        title="Posible laguna: Test",
        description="desc",
        evidence=[],
        target_entities=target_entities,
        confidence=0.7,
        priority=1,
        status=status,
        source_event_id="trace-1",
    )
    return recommendation_id


async def test_has_pending_recommendation_detecta_duplicado() -> None:
    engine = create_engine(get_settings())
    target_entities = [f"node-{uuid.uuid4().hex[:8]}"]
    recommendation_id = await _insert(engine, target_entities=target_entities)
    try:
        assert (
            await postgres_storage.has_pending_recommendation(
                engine, type="gap", target_entities=target_entities
            )
            is True
        )
        assert (
            await postgres_storage.has_pending_recommendation(
                engine, type="contradiction", target_entities=target_entities
            )
            is False
        )
        assert (
            await postgres_storage.has_pending_recommendation(
                engine, type="gap", target_entities=["otro-node"]
            )
            is False
        )
    finally:
        await _cleanup(engine, [recommendation_id])


async def test_has_pending_recommendation_ignora_no_pendientes() -> None:
    engine = create_engine(get_settings())
    target_entities = [f"node-{uuid.uuid4().hex[:8]}"]
    recommendation_id = await _insert(engine, target_entities=target_entities, status="dismissed")
    try:
        assert (
            await postgres_storage.has_pending_recommendation(
                engine, type="gap", target_entities=target_entities
            )
            is False
        )
    finally:
        await _cleanup(engine, [recommendation_id])


async def test_list_recommendations_filtra_por_type_y_status_con_paginacion() -> None:
    engine = create_engine(get_settings())
    gap_id = await _insert(engine, target_entities=[f"node-{uuid.uuid4().hex[:8]}"])
    other_id = uuid.uuid4()
    await postgres_storage.insert_recommendation(
        engine,
        recommendation_id=other_id,
        type="contradiction",
        title="Contradicción de prueba",
        description="",
        evidence=[],
        target_entities=[f"node-{uuid.uuid4().hex[:8]}"],
        confidence=0.5,
        priority=0,
        status="dismissed",
        source_event_id=None,
    )
    try:
        gaps, _next_cursor = await postgres_storage.list_recommendations(
            engine, type="gap", status="pending", limit=20
        )
        assert gap_id in {row["recommendation_id"] for row in gaps}
        assert other_id not in {row["recommendation_id"] for row in gaps}

        dismissed, _ = await postgres_storage.list_recommendations(
            engine, status="dismissed", limit=20
        )
        assert other_id in {row["recommendation_id"] for row in dismissed}
    finally:
        await _cleanup(engine, [gap_id, other_id])


async def test_list_recommendations_pagina_con_cursor() -> None:
    """`recommendation_id` es un UUID aleatorio (no secuencial): el orden entre
    dos filas propias es impredecible si ya hay otras recomendaciones reales
    en la tabla — se prueba la propiedad de paginación (avanzar con el cursor
    hasta ver ambos ids, sin duplicados), no una posición exacta."""
    engine = create_engine(get_settings())
    ids = {
        await _insert(engine, target_entities=[f"node-{uuid.uuid4().hex[:8]}"]),
        await _insert(engine, target_entities=[f"node-{uuid.uuid4().hex[:8]}"]),
    }
    try:
        seen: set[uuid.UUID] = set()
        cursor: uuid.UUID | None = None
        for _ in range(1000):  # tope defensivo: nunca debería iterar tanto
            page, cursor = await postgres_storage.list_recommendations(
                engine, cursor=cursor, limit=1
            )
            if not page:
                break
            seen.update(row["recommendation_id"] for row in page)
            if ids <= seen:
                break
        assert ids <= seen
    finally:
        await _cleanup(engine, list(ids))
