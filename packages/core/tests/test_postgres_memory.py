"""Memoria contra Postgres real (Sprint 12, doc 04 §2, doc 06 §2 `/v1/memory`).

Requiere `make up` (Postgres arriba) y la migración 0006 aplicada. Corre solo
con `-m integration` — Sprint 8/9/10/11 dejaron la lección de que los mocks no
atrapan bugs de tipos SQL/Cypher reales.
"""

from __future__ import annotations

import uuid

import pytest

from kos_core.config import get_settings
from kos_core.storage import postgres as postgres_storage
from kos_core.storage.postgres import create_engine

pytestmark = pytest.mark.integration


async def _cleanup(engine: object, memory_ids: list[uuid.UUID]) -> None:
    from sqlalchemy import delete

    from kos_core.storage.postgres import memory_items_table

    async with engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.execute(
            delete(memory_items_table).where(memory_items_table.c.memory_id.in_(memory_ids))
        )


async def test_insert_get_y_archive_memory() -> None:
    engine = create_engine(get_settings())
    memory_id = uuid.uuid4()
    try:
        await postgres_storage.insert_memory(
            engine,
            memory_id=memory_id,
            type="episodic",
            content="Preguntó: 'kubernetes' → usa siempre Railway",
            embedding=[0.1] * 1024,
            entities=[],
            sources=["doc-a"],
            confidence=0.8,
            salience=0.5,
        )

        fetched = await postgres_storage.get_memory(engine, memory_id)
        assert fetched is not None
        assert fetched["type"] == "episodic"
        assert fetched["sources"] == ["doc-a"]
        assert fetched["archived_at"] is None
        assert "embedding" not in fetched  # auditoría no expone el vector (doc 06 §2)

        assert await postgres_storage.archive_memory(engine, memory_id) is True
        archived = await postgres_storage.get_memory(engine, memory_id)
        assert archived is not None
        assert archived["archived_at"] is not None

        # Ya archivada: un segundo archive es un no-op (no hay nada más que olvidar).
        assert await postgres_storage.archive_memory(engine, memory_id) is False
    finally:
        await _cleanup(engine, [memory_id])
        await engine.dispose()


async def test_archive_memory_inexistente_devuelve_false() -> None:
    engine = create_engine(get_settings())
    try:
        assert await postgres_storage.archive_memory(engine, uuid.uuid4()) is False
    finally:
        await engine.dispose()


async def test_list_memories_filtra_tipo_query_y_excluye_archivadas() -> None:
    engine = create_engine(get_settings())
    marker = uuid.uuid4().hex[:8]
    episodic_id, semantic_id, archived_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        await postgres_storage.insert_memory(
            engine,
            memory_id=episodic_id,
            type="episodic",
            content=f"Preguntó por kubernetes-{marker}",
            embedding=None,
            entities=[],
            sources=["doc-a"],
            confidence=0.8,
            salience=0.5,
        )
        await postgres_storage.insert_memory(
            engine,
            memory_id=semantic_id,
            type="semantic",
            content=f"Le interesa kubernetes-{marker}",
            embedding=None,
            entities=[],
            sources=["doc-a"],
            confidence=0.9,
            salience=0.6,
        )
        await postgres_storage.insert_memory(
            engine,
            memory_id=archived_id,
            type="episodic",
            content=f"Preguntó por algo viejo-{marker}",
            embedding=None,
            entities=[],
            sources=["doc-b"],
            confidence=0.5,
            salience=0.3,
        )
        await postgres_storage.archive_memory(engine, archived_id)

        by_type, _ = await postgres_storage.list_memories(engine, type="semantic", limit=100)
        assert {row["memory_id"] for row in by_type} & {episodic_id, semantic_id, archived_id} == {
            semantic_id
        }

        by_query, _ = await postgres_storage.list_memories(engine, q=marker, limit=100)
        assert {row["memory_id"] for row in by_query} == {episodic_id, semantic_id}

        with_archived, _ = await postgres_storage.list_memories(
            engine, q=marker, include_archived=True, limit=100
        )
        assert {row["memory_id"] for row in with_archived} == {
            episodic_id,
            semantic_id,
            archived_id,
        }
    finally:
        await _cleanup(engine, [episodic_id, semantic_id, archived_id])
        await engine.dispose()


async def test_list_unconsolidated_episodic_y_mark_superseded() -> None:
    engine = create_engine(get_settings())
    plain_id, superseded_id, semantic_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        await postgres_storage.insert_memory(
            engine,
            memory_id=plain_id,
            type="episodic",
            content="episódica activa",
            embedding=[0.2] * 1024,
            entities=[],
            sources=["doc-a"],
            confidence=0.7,
            salience=0.5,
        )
        await postgres_storage.insert_memory(
            engine,
            memory_id=superseded_id,
            type="episodic",
            content="episódica ya fusionada",
            embedding=[0.3] * 1024,
            entities=[],
            sources=["doc-b"],
            confidence=0.7,
            salience=0.5,
        )
        await postgres_storage.insert_memory(
            engine,
            memory_id=semantic_id,
            type="semantic",
            content="semántica",
            embedding=[0.4] * 1024,
            entities=[],
            sources=["doc-a", "doc-b"],
            confidence=0.9,
            salience=0.7,
        )

        before = await postgres_storage.list_unconsolidated_episodic(engine)
        assert {row["memory_id"] for row in before} >= {plain_id, superseded_id}
        assert semantic_id not in {row["memory_id"] for row in before}

        updated = await postgres_storage.mark_superseded(
            engine, [superseded_id], superseded_by=semantic_id
        )
        assert updated == 1

        after = await postgres_storage.list_unconsolidated_episodic(engine)
        after_ids = {row["memory_id"] for row in after}
        assert plain_id in after_ids
        assert superseded_id not in after_ids

        fetched = await postgres_storage.get_memory(engine, superseded_id)
        assert fetched is not None
        assert fetched["superseded_by"] == semantic_id
    finally:
        await _cleanup(engine, [plain_id, superseded_id, semantic_id])
        await engine.dispose()
