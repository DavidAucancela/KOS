"""`similarity_band_chunks` contra Postgres real (Sprint 24, doc 11 §4):
candidatos de contradicción — chunks de OTROS documentos en una banda de
similitud intermedia (temáticamente relacionados, no casi-duplicados).

Requiere `make up` (Postgres arriba) y migraciones al día. Corre solo con
`-m integration` — mismo motivo que `test_neo4j_gaps_integration.py`/
`test_postgres_recommendations.py`: los mocks no atrapan bugs de pgvector
reales. Usa embeddings sintéticos (no Ollama) para controlar la similitud
exacta entre fixtures: vectores unitarios en un subespacio 2D de
`EMBEDDING_DIM` dimensiones — la similitud coseno entre dos vectores
unitarios es `cos(ángulo)`, independiente de la magnitud, así que alcanza con
elegir el ángulo para obtener la similitud deseada.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete

from kos_core.config import get_settings
from kos_core.storage.postgres import (
    EMBEDDING_DIM,
    chunks_table,
    create_engine,
    documents_table,
)
from kos_core.storage.search import similarity_band_chunks

pytestmark = pytest.mark.integration

_FLOOR = 0.75
_CEILING = 0.92


def _unit_vector(angle_degrees: float) -> list[float]:
    radians = math.radians(angle_degrees)
    vector = [math.cos(radians), math.sin(radians)] + [0.0] * (EMBEDDING_DIM - 2)
    return vector


async def _insert_document(engine: object, *, doc_id: uuid.UUID, source_id: str) -> None:
    async with engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.execute(
            documents_table.insert().values(
                doc_id=doc_id,
                connector="test",
                source_id=source_id,
                title=f"Doc {source_id}",
                fetched_at=datetime.now(UTC),
            )
        )


async def _insert_chunk(
    engine: object, *, chunk_id: uuid.UUID, doc_id: uuid.UUID, text: str, embedding: list[float]
) -> None:
    async with engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.execute(
            chunks_table.insert().values(
                chunk_id=chunk_id,
                doc_id=doc_id,
                text=text,
                position=0,
                embedding=embedding,
            )
        )


async def _cleanup(engine: object, doc_ids: list[uuid.UUID]) -> None:
    async with engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.execute(chunks_table.delete().where(chunks_table.c.doc_id.in_(doc_ids)))
        await conn.execute(delete(documents_table).where(documents_table.c.doc_id.in_(doc_ids)))


async def test_similarity_band_chunks_incluye_solo_la_banda_intermedia() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    suffix = uuid.uuid4().hex[:8]
    seed_doc = uuid.uuid4()
    band_doc = uuid.uuid4()
    duplicate_doc = uuid.uuid4()
    unrelated_doc = uuid.uuid4()
    doc_ids = [seed_doc, band_doc, duplicate_doc, unrelated_doc]
    try:
        await _insert_document(engine, doc_id=seed_doc, source_id=f"seed-{suffix}")
        await _insert_document(engine, doc_id=band_doc, source_id=f"band-{suffix}")
        await _insert_document(engine, doc_id=duplicate_doc, source_id=f"dup-{suffix}")
        await _insert_document(engine, doc_id=unrelated_doc, source_id=f"unrelated-{suffix}")

        seed_chunk_id = uuid.uuid4()
        await _insert_chunk(
            engine,
            chunk_id=seed_chunk_id,
            doc_id=seed_doc,
            text="Redis persiste todo a disco por defecto.",
            embedding=_unit_vector(0.0),
        )
        # cos(31.79°) ≈ 0.85 — dentro de la banda (0.75, 0.92).
        band_chunk_id = uuid.uuid4()
        await _insert_chunk(
            engine,
            chunk_id=band_chunk_id,
            doc_id=band_doc,
            text="Redis nunca persiste nada a disco.",
            embedding=_unit_vector(31.79),
        )
        # cos(18.19°) ≈ 0.95 — por encima del techo (duplicado, no contradicción).
        await _insert_chunk(
            engine,
            chunk_id=uuid.uuid4(),
            doc_id=duplicate_doc,
            text="Redis persiste todo a disco (casi idéntico).",
            embedding=_unit_vector(18.19),
        )
        # cos(72.54°) ≈ 0.30 — por debajo del piso (sin relación temática).
        await _insert_chunk(
            engine,
            chunk_id=uuid.uuid4(),
            doc_id=unrelated_doc,
            text="El clima en Buenos Aires es templado.",
            embedding=_unit_vector(72.54),
        )
        # Mismo doc que la semilla, altísima similitud: debe excluirse por
        # `exclude_doc_id` aunque caiga fuera de la banda igual.
        await _insert_chunk(
            engine,
            chunk_id=uuid.uuid4(),
            doc_id=seed_doc,
            text="Redis persiste todo a disco (misma nota).",
            embedding=_unit_vector(0.0),
        )

        matches = await similarity_band_chunks(
            engine,
            _unit_vector(0.0),
            exclude_doc_id=seed_doc,
            floor=_FLOOR,
            ceiling=_CEILING,
            limit=10,
        )

        assert [hit.chunk_id for hit in matches] == [band_chunk_id]
        assert matches[0].doc_id == band_doc
        assert _FLOOR < matches[0].score < _CEILING
    finally:
        await _cleanup(engine, doc_ids)
        await engine.dispose()
