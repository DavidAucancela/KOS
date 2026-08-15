"""Tests de las tasks de memoria (Sprint 12, doc 04): storage mockeado, sin
Postgres ni Ollama reales — mismo estilo que `test_graph_sync_task.py`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from kos_core.storage import postgres as postgres_module
from kos_workers.celery_app import app
from kos_workers.tasks import memory as memory_module

_NOW = datetime.now(UTC)


def _memory(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
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
        "embedding": [1.0, 0.0, 0.0],
    }
    base.update(overrides)
    return base


async def test_learn_core_guarda_memoria_episodica(monkeypatch: pytest.MonkeyPatch) -> None:
    inserted: list[dict[str, Any]] = []

    async def fake_insert(engine: Any, **kwargs: Any) -> None:
        inserted.append(kwargs)

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        assert len(texts) == 1
        return [[0.1, 0.2, 0.3]]

    async def fake_resolve_entities(doc_ids: list[str]) -> list[str]:
        return []

    monkeypatch.setattr(postgres_module, "insert_memory", fake_insert)

    result = await memory_module._learn_core(
        None,
        query="¿qué es KOS?",
        answer="un motor de conocimiento",
        sources=["doc-a"],
        confidence=0.9,
        embed=fake_embed,
        resolve_entities=fake_resolve_entities,
    )

    assert uuid.UUID(result["memory_id"])
    [call] = inserted
    assert call["type"] == "episodic"
    assert call["content"] == "Preguntó: '¿qué es KOS?' → un motor de conocimiento"
    assert call["embedding"] == [0.1, 0.2, 0.3]
    assert call["sources"] == [{"doc_id": "doc-a", "confidence": 0.9}]
    assert call["confidence"] == 0.9
    assert call["salience"] == memory_module.INITIAL_SALIENCE
    assert call["entities"] == []


async def test_learn_core_resuelve_entities_por_sources_compartidas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprint 13 (doc 04 §2): entities[] sale de nodos que ya comparten sources[]
    con la memoria — sin extracción LLM nueva."""
    inserted: list[dict[str, Any]] = []
    resolve_calls: list[list[str]] = []

    async def fake_insert(engine: Any, **kwargs: Any) -> None:
        inserted.append(kwargs)

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3]]

    async def fake_resolve_entities(doc_ids: list[str]) -> list[str]:
        resolve_calls.append(doc_ids)
        return ["node-fastapi", "node-railway"]

    monkeypatch.setattr(postgres_module, "insert_memory", fake_insert)

    await memory_module._learn_core(
        None,
        query="¿qué uso para deploy?",
        answer="Railway",
        sources=["doc-a", "doc-b"],
        confidence=0.9,
        embed=fake_embed,
        resolve_entities=fake_resolve_entities,
    )

    assert resolve_calls == [["doc-a", "doc-b"]]
    [call] = inserted
    assert call["entities"] == ["node-fastapi", "node-railway"]


def test_cluster_by_similarity_agrupa_por_encima_del_umbral() -> None:
    similar_a = _memory(embedding=[1.0, 0.0])
    similar_b = _memory(embedding=[0.999, 0.001])
    distinta = _memory(embedding=[0.0, 1.0])

    clusters = memory_module._cluster_by_similarity([similar_a, similar_b, distinta])

    sizes = sorted(len(cluster) for cluster in clusters)
    assert sizes == [1, 2]


async def test_consolidate_core_crea_semantica_desde_tres_episodicas_similares(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cluster = [
        _memory(
            embedding=[1.0, 0.0],
            content=f"Preguntó: 'kubernetes {i}'",
            created_at=_NOW - timedelta(days=i),
            sources=[{"doc_id": f"doc-{i}", "confidence": 0.7}],
            confidence=0.7,
            salience=0.5,
        )
        for i in range(3)
    ]

    async def fake_list_unconsolidated(engine: Any) -> list[dict[str, Any]]:
        return cluster

    inserted: list[dict[str, Any]] = []

    async def fake_insert(engine: Any, **kwargs: Any) -> None:
        inserted.append(kwargs)

    superseded_calls: list[dict[str, Any]] = []

    async def fake_mark_superseded(
        engine: Any, memory_ids: list[uuid.UUID], *, superseded_by: uuid.UUID
    ) -> int:
        superseded_calls.append({"memory_ids": memory_ids, "superseded_by": superseded_by})
        return len(memory_ids)

    monkeypatch.setattr(postgres_module, "list_unconsolidated_episodic", fake_list_unconsolidated)
    monkeypatch.setattr(postgres_module, "insert_memory", fake_insert)
    monkeypatch.setattr(postgres_module, "mark_superseded", fake_mark_superseded)

    result = await memory_module._consolidate_core(None)

    assert result == {"episodic_seen": 3, "semantic_created": 1}
    [semantic] = inserted
    assert semantic["type"] == "semantic"
    assert semantic["sources"] == [
        {"doc_id": "doc-0", "confidence": 0.7},
        {"doc_id": "doc-1", "confidence": 0.7},
        {"doc_id": "doc-2", "confidence": 0.7},
    ]
    assert semantic["confidence"] == pytest.approx(0.7 + memory_module.CONSOLIDATED_BOOST)
    [superseded] = superseded_calls
    assert set(superseded["memory_ids"]) == {m["memory_id"] for m in cluster}


async def test_consolidate_core_no_agrupa_menos_de_tres(monkeypatch: pytest.MonkeyPatch) -> None:
    two = [_memory(embedding=[1.0, 0.0]), _memory(embedding=[1.0, 0.0])]

    async def fake_list_unconsolidated(engine: Any) -> list[dict[str, Any]]:
        return two

    async def fail_insert(engine: Any, **kwargs: Any) -> None:
        raise AssertionError("no debe crear semántica con menos de MIN_CLUSTER_SIZE")

    monkeypatch.setattr(postgres_module, "list_unconsolidated_episodic", fake_list_unconsolidated)
    monkeypatch.setattr(postgres_module, "insert_memory", fail_insert)

    result = await memory_module._consolidate_core(None)

    assert result == {"episodic_seen": 2, "semantic_created": 0}


def test_las_tasks_estan_registradas_con_nombre_de_evento() -> None:
    assert "kos.memory_learn" in app.tasks
    assert "kos.memory_consolidate" in app.tasks
