"""Regresión: `retire_documents` no debe cruzar fuentes que comparten conector.

Bug real (Sprint 6, 2026-07-18): dos fuentes "obsidian" distintas (el vault real
del usuario y un vault de prueba) comparten `connector="obsidian"`. Sin filtrar
por `source_uuid`, `kos reindex` sobre la fuente pequeña marcaba como "borrados"
(tombstone) los ~690 documentos de la fuente grande, borrando sus chunks.
Requiere Postgres real (`make up`); corre solo con `-m integration`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select

from kos_core.config import get_settings
from kos_core.storage.postgres import (
    create_engine,
    documents_table,
    retire_documents,
    sources_table,
)

pytestmark = pytest.mark.integration

_CONNECTOR = "test-connector-retire"


async def test_retire_documents_no_cruza_fuentes_con_mismo_conector() -> None:
    engine = create_engine(get_settings())
    source_a, source_b = uuid.uuid4(), uuid.uuid4()
    doc_a, doc_b = uuid.uuid4(), uuid.uuid4()
    try:
        async with engine.begin() as conn:
            for source_uuid, name in ((source_a, "test-source-a"), (source_b, "test-source-b")):
                await conn.execute(
                    insert(sources_table).values(
                        source_uuid=source_uuid, name=name, connector=_CONNECTOR
                    )
                )
            for doc_id, source_uuid, source_id in (
                (doc_a, source_a, "note-a.md"),
                (doc_b, source_b, "note-b.md"),
            ):
                await conn.execute(
                    insert(documents_table).values(
                        doc_id=doc_id,
                        source_uuid=source_uuid,
                        connector=_CONNECTOR,
                        source_id=source_id,
                        content_hash="hash",
                        fetched_at=datetime.now(UTC),
                    )
                )

        # Simula el bug real: se pasan AMBOS source_ids como "ausentes" (como
        # habría calculado _known_hashes sin filtrar por source_uuid), pero se
        # pide retirar solo en nombre de la fuente B. Sin el filtro de
        # source_uuid en el WHERE, "note-a.md" (de la fuente A) también se
        # habría retirado por error.
        retired = await retire_documents(
            engine,
            source_uuid=source_b,
            connector=_CONNECTOR,
            source_ids={"note-a.md", "note-b.md"},
        )
        assert retired == [doc_b]

        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    select(documents_table.c.doc_id, documents_table.c.deleted_at).where(
                        documents_table.c.doc_id.in_([doc_a, doc_b])
                    )
                )
            ).all()
        deleted_at_by_doc = {row.doc_id: row.deleted_at for row in rows}
        assert deleted_at_by_doc[doc_a] is None  # fuente A: intacto (el bug lo hubiera retirado)
        assert deleted_at_by_doc[doc_b] is not None  # fuente B: retirado, es lo pedido
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                documents_table.delete().where(documents_table.c.doc_id.in_([doc_a, doc_b]))
            )
            await conn.execute(
                sources_table.delete().where(sources_table.c.source_uuid.in_([source_a, source_b]))
            )
        await engine.dispose()
