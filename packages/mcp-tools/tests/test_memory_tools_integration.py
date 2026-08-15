"""Tests de integración de `kos_mcp.tools.memory` contra Postgres + Neo4j +
Ollama reales (Sprint 16). Requiere `make up` y Ollama nativo. Corre solo con
`-m integration`."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage.postgres import create_engine, memory_items_table
from kos_mcp.tools import memory as memory_tools

pytestmark = pytest.mark.integration


async def _cleanup_memory(engine: object, memory_ids: list[uuid.UUID]) -> None:
    async with engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.execute(
            delete(memory_items_table).where(memory_items_table.c.memory_id.in_(memory_ids))
        )


async def test_store_core_sin_confirm_no_persiste_nada() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    driver = neo4j_storage.create_driver(settings)
    marker = uuid.uuid4().hex[:8]
    try:
        result = await memory_tools._store_core(
            engine,
            driver,
            lambda texts: None,  # no debe llamarse: el gate corta antes del embed
            query=f"[{marker}] pregunta de prueba",
            answer="respuesta",
            sources=[],
            confidence=0.5,
            confirm=False,
            trace_id="test-trace",
        )
        assert result.approved is False
        assert result.memory_id is None
    finally:
        await driver.close()
        await engine.dispose()


async def test_store_core_con_confirm_y_recall_core_contra_infra_real() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    driver = neo4j_storage.create_driver(settings)
    embedder = OllamaEmbeddingClient(settings)
    marker = uuid.uuid4().hex[:8]
    memory_id: uuid.UUID | None = None
    try:
        store_result = await memory_tools._store_core(
            engine,
            driver,
            embedder.embed,
            query=f"[{marker}] pregunta de prueba",
            answer="respuesta de prueba",
            sources=[],
            confidence=0.5,
            confirm=True,
            trace_id="test-trace",
        )
        assert store_result.approved is True
        assert store_result.memory_id is not None
        memory_id = store_result.memory_id

        recall_result = await memory_tools._recall_core(engine, None, marker, None, 20)
        assert any(item.memory_id == memory_id for item in recall_result.items)
    finally:
        if memory_id is not None:
            await _cleanup_memory(engine, [memory_id])
        await driver.close()
        await embedder.aclose()
        await engine.dispose()
