"""Test de integración de `kos_mcp.tools.vector` contra Postgres + Ollama reales
(Sprint 16). Requiere `make up` y Ollama nativo. Corre solo con `-m integration`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete

from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.storage.postgres import chunks_table, create_engine, documents_table
from kos_mcp.tools import vector as vector_tools

pytestmark = pytest.mark.integration


async def _cleanup(engine: object, doc_id: uuid.UUID) -> None:
    async with engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.execute(delete(chunks_table).where(chunks_table.c.doc_id == doc_id))
        await conn.execute(delete(documents_table).where(documents_table.c.doc_id == doc_id))


async def test_search_core_contra_infra_real() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    embedder = OllamaEmbeddingClient(settings)
    doc_id = uuid.uuid4()
    marker = uuid.uuid4().hex[:8]
    try:
        async with engine.begin() as conn:
            await conn.execute(
                documents_table.insert().values(
                    doc_id=doc_id,
                    connector="test",
                    source_id=f"test-mcp-vector-{marker}.md",
                    title=f"Nota sobre {marker}",
                    fetched_at=datetime.now(UTC),
                )
            )
            await conn.execute(
                chunks_table.insert().values(
                    chunk_id=uuid.uuid4(),
                    doc_id=doc_id,
                    text=f"contenido de prueba {marker} sobre búsqueda híbrida",
                    position=0,
                )
            )

        result = await vector_tools._search_core(engine, embedder.embed, marker, 5, "hybrid", None)

        assert any(marker in (ev.quote or "") for ev in result.evidence)
        assert result.degraded is False
    finally:
        await _cleanup(engine, doc_id)
        await embedder.aclose()
        await engine.dispose()
