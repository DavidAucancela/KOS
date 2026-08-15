"""Tests de integración de `kos_mcp.tools.docs` contra Postgres real (Sprint 16).
Requiere `make up`. Corre solo con `-m integration`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete

from kos_core.config import get_settings
from kos_core.storage.postgres import chunks_table, create_engine, documents_table
from kos_mcp.tools import docs as docs_tools

pytestmark = pytest.mark.integration


async def _cleanup(engine: object, doc_id: uuid.UUID) -> None:
    async with engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.execute(delete(chunks_table).where(chunks_table.c.doc_id == doc_id))
        await conn.execute(delete(documents_table).where(documents_table.c.doc_id == doc_id))


async def test_read_document_core_contra_postgres_real() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    doc_id = uuid.uuid4()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                documents_table.insert().values(
                    doc_id=doc_id,
                    connector="test",
                    source_id=f"test-mcp-docs-{uuid.uuid4().hex[:8]}.md",
                    title="Documento de prueba MCP",
                    summary="resumen",
                    fetched_at=datetime.now(UTC),
                )
            )
            await conn.execute(
                chunks_table.insert(),
                [
                    {
                        "chunk_id": uuid.uuid4(),
                        "doc_id": doc_id,
                        "text": "primer chunk",
                        "position": 0,
                    },
                    {
                        "chunk_id": uuid.uuid4(),
                        "doc_id": doc_id,
                        "text": "segundo chunk",
                        "position": 1,
                    },
                ],
            )

        result = await docs_tools._read_document_core(engine, str(doc_id), None, 20)

        assert result.title == "Documento de prueba MCP"
        assert result.text == "primer chunk\n\nsegundo chunk"
        assert len(result.evidence) == 2
    finally:
        await _cleanup(engine, doc_id)
        await engine.dispose()
