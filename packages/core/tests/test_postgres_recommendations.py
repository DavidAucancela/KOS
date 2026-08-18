"""Recomendaciones contra Postgres real (Sprint 22/23/25, doc 11 §2/§6/§7/§8).

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


async def test_has_active_recommendation_detecta_duplicado() -> None:
    engine = create_engine(get_settings())
    target_entities = [f"node-{uuid.uuid4().hex[:8]}"]
    recommendation_id = await _insert(engine, target_entities=target_entities)
    try:
        assert (
            await postgres_storage.has_active_recommendation(
                engine, type="gap", target_entities=target_entities
            )
            is True
        )
        assert (
            await postgres_storage.has_active_recommendation(
                engine, type="contradiction", target_entities=target_entities
            )
            is False
        )
        assert (
            await postgres_storage.has_active_recommendation(
                engine, type="gap", target_entities=["otro-node"]
            )
            is False
        )
    finally:
        await _cleanup(engine, [recommendation_id])


async def test_has_active_recommendation_bloquea_dismissed_y_accepted() -> None:
    """Sprint 25, doc 11 §8: descartar debe suprimir la regeneración
    inmediata con la misma firma — antes de este sprint, `dismissed` dejaba
    la firma libre para que la siguiente pasada la volviera a proponer."""
    engine = create_engine(get_settings())
    dismissed_entities = [f"node-{uuid.uuid4().hex[:8]}"]
    accepted_entities = [f"node-{uuid.uuid4().hex[:8]}"]
    dismissed_id = await _insert(engine, target_entities=dismissed_entities, status="dismissed")
    accepted_id = await _insert(engine, target_entities=accepted_entities, status="accepted")
    try:
        assert (
            await postgres_storage.has_active_recommendation(
                engine, type="gap", target_entities=dismissed_entities
            )
            is True
        )
        assert (
            await postgres_storage.has_active_recommendation(
                engine, type="gap", target_entities=accepted_entities
            )
            is True
        )
    finally:
        await _cleanup(engine, [dismissed_id, accepted_id])


async def test_has_active_recommendation_no_bloquea_expired_ni_superseded() -> None:
    engine = create_engine(get_settings())
    expired_entities = [f"node-{uuid.uuid4().hex[:8]}"]
    superseded_entities = [f"node-{uuid.uuid4().hex[:8]}"]
    expired_id = await _insert(engine, target_entities=expired_entities, status="expired")
    superseded_id = await _insert(engine, target_entities=superseded_entities, status="superseded")
    try:
        assert (
            await postgres_storage.has_active_recommendation(
                engine, type="gap", target_entities=expired_entities
            )
            is False
        )
        assert (
            await postgres_storage.has_active_recommendation(
                engine, type="gap", target_entities=superseded_entities
            )
            is False
        )
    finally:
        await _cleanup(engine, [expired_id, superseded_id])


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


async def test_update_recommendation_status_descarta_con_razon() -> None:
    engine = create_engine(get_settings())
    recommendation_id = await _insert(engine, target_entities=[f"node-{uuid.uuid4().hex[:8]}"])
    try:
        updated = await postgres_storage.update_recommendation_status(
            engine, recommendation_id, status="dismissed", dismissed_reason="ya lo sabía"
        )
        assert updated is not None
        assert updated["status"] == "dismissed"
        assert updated["dismissed_reason"] == "ya lo sabía"
        assert updated["resolved_at"] is not None
    finally:
        await _cleanup(engine, [recommendation_id])


async def test_update_recommendation_status_acepta_sin_razon() -> None:
    engine = create_engine(get_settings())
    recommendation_id = await _insert(engine, target_entities=[f"node-{uuid.uuid4().hex[:8]}"])
    try:
        updated = await postgres_storage.update_recommendation_status(
            engine, recommendation_id, status="accepted", dismissed_reason=None
        )
        assert updated is not None
        assert updated["status"] == "accepted"
        assert updated["dismissed_reason"] is None
    finally:
        await _cleanup(engine, [recommendation_id])


async def test_update_recommendation_status_no_reescribe_ya_resuelta() -> None:
    """Idempotente contra doble-click (mismo criterio que `archive_memory`):
    una vez resuelta, un segundo PATCH no la vuelve a tocar."""
    engine = create_engine(get_settings())
    recommendation_id = await _insert(engine, target_entities=[f"node-{uuid.uuid4().hex[:8]}"])
    try:
        first = await postgres_storage.update_recommendation_status(
            engine, recommendation_id, status="dismissed", dismissed_reason="primera vez"
        )
        assert first is not None

        second = await postgres_storage.update_recommendation_status(
            engine, recommendation_id, status="accepted", dismissed_reason=None
        )
        assert second is None
    finally:
        await _cleanup(engine, [recommendation_id])


async def test_update_recommendation_status_inexistente_devuelve_none() -> None:
    engine = create_engine(get_settings())
    result = await postgres_storage.update_recommendation_status(
        engine, uuid.uuid4(), status="accepted", dismissed_reason=None
    )
    assert result is None


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
