"""Tests unitarios de `kos_mcp.tools.memory` (Sprint 16): storage mockeado."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from kos_core.memory_learn import learn_from_query_answer as _real_learn_from_query_answer
from kos_core.storage import postgres as postgres_module
from kos_mcp.tools import memory as memory_tools

_NOW = datetime.now(UTC)

_MEMORY_ROW = {
    "memory_id": uuid.uuid4(),
    "type": "episodic",
    "content": "Preguntó: 'kubernetes' → usa siempre Railway",
    "entities": [],
    "sources": [{"doc_id": "doc-a", "confidence": 0.8}],
    "confidence": 0.8,
    "salience": 0.5,
    "created_at": _NOW,
    "last_accessed_at": _NOW,
    "archived_at": None,
    "superseded_by": None,
}


async def test_recall_core_devuelve_pagina(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_list_memories(engine: Any, **kwargs: Any) -> tuple[list[dict], None]:
        return [_MEMORY_ROW], None

    monkeypatch.setattr(postgres_module, "list_memories", fake_list_memories)

    result = await memory_tools._recall_core(None, None, None, None, 20)

    assert len(result.items) == 1
    assert result.items[0].content.startswith("Preguntó")
    assert result.next_cursor is None


async def test_store_core_sin_confirm_no_escribe(monkeypatch: pytest.MonkeyPatch) -> None:
    proposals: list[dict[str, Any]] = []

    async def fail_insert(engine: Any, **kwargs: Any) -> None:
        raise AssertionError("no debe escribir sin confirm=True")

    async def fake_insert_proposal(engine: Any, **kwargs: Any) -> None:
        proposals.append(kwargs)

    monkeypatch.setattr(postgres_module, "insert_memory", fail_insert)
    monkeypatch.setattr(postgres_module, "insert_memory_proposal", fake_insert_proposal)

    result = await memory_tools._store_core(
        None,
        None,
        lambda texts: None,
        query="¿qué es KOS?",
        answer="un motor de conocimiento",
        sources=["doc-a"],
        confidence=0.9,
        confirm=False,
        trace_id="trace-1",
    )

    assert result.approved is False
    assert result.memory_id is None
    assert "confirm=true" in result.message
    assert result.proposal_id is not None
    [proposal] = proposals
    assert proposal["query"] == "¿qué es KOS?"
    assert proposal["proposal_id"] == result.proposal_id


async def test_store_core_con_confirm_escribe(monkeypatch: pytest.MonkeyPatch) -> None:
    inserted: list[dict[str, Any]] = []

    async def fake_insert(engine: Any, **kwargs: Any) -> None:
        inserted.append(kwargs)

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3]]

    async def fake_find_node_ids(driver: Any, doc_ids: list[str]) -> list[str]:
        return ["node-1"]

    monkeypatch.setattr(postgres_module, "insert_memory", fake_insert)
    monkeypatch.setattr("kos_core.storage.neo4j.find_node_ids_by_sources", fake_find_node_ids)

    result = await memory_tools._store_core(
        None,
        None,
        fake_embed,
        query="¿qué es KOS?",
        answer="un motor de conocimiento",
        sources=["doc-a"],
        confidence=0.9,
        confirm=True,
        trace_id="trace-1",
    )

    assert result.approved is True
    assert result.memory_id is not None
    [call] = inserted
    assert call["entities"] == ["node-1"]
    assert call["sources"] == [{"doc_id": "doc-a", "confidence": 0.9}]


def test_learn_from_query_answer_es_la_misma_funcion_promovida() -> None:
    """Confirma que memory.store reusa exactamente la lógica promovida en
    Sprint 16 (doc 04 §3), no una copia."""
    assert memory_tools.learn_from_query_answer is _real_learn_from_query_answer
