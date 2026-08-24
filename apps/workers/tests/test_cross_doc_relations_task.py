"""Tests de la task de relaciones cross-documento (doc 12 §4): pgvector y
Neo4j mockeados, sin infra real — mismo estilo que `test_recommend_task.py`."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from kos_core.storage import neo4j as neo4j_module
from kos_core.storage import postgres as postgres_module
from kos_core.storage import search as search_module
from kos_core.storage.search import SearchHit
from kos_workers.celery_app import app
from kos_workers.tasks import cross_doc_relations as cross_doc_module


def _chunk(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "chunk_id": uuid.uuid4(),
        "doc_id": uuid.uuid4(),
        "text": "FastAPI se integra con Pydantic.",
        "embedding": [0.1, 0.2, 0.3],
        "entity_node_ids": ["node-a"],
    }
    base.update(overrides)
    return base


def _match_hit(**overrides: Any) -> SearchHit:
    base: dict[str, Any] = {
        "chunk_id": uuid.uuid4(),
        "doc_id": uuid.uuid4(),
        "text": "Pydantic valida los modelos de FastAPI.",
        "score": 0.85,
        "source": "vector",
    }
    base.update(overrides)
    return SearchHit.model_validate(base)


async def _no_generate(prompt: str) -> str:
    raise AssertionError("no debe llamarse al LLM")


async def test_sin_match_en_banda_no_llama_al_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    own = _chunk()

    async def fake_get_chunk(engine: Any, chunk_id: Any) -> dict[str, Any]:
        return own

    async def fake_band(engine: Any, embedding: Any, **kwargs: Any) -> list[SearchHit]:
        return []

    monkeypatch.setattr(postgres_module, "get_chunk", fake_get_chunk)
    monkeypatch.setattr(search_module, "similarity_band_chunks", fake_band)

    checked, written = await cross_doc_module._discover_for_chunk(
        None, None, _no_generate, own_doc_id=str(own["doc_id"]), chunk_id=str(own["chunk_id"])
    )

    assert (checked, written) == (False, 0)


async def test_vecino_sin_entidades_resueltas_se_saltea(monkeypatch: pytest.MonkeyPatch) -> None:
    own = _chunk()
    match = _match_hit()
    other = _chunk(chunk_id=match.chunk_id, doc_id=match.doc_id, entity_node_ids=[])

    calls = {"n": 0}

    async def fake_get_chunk(engine: Any, chunk_id: Any) -> dict[str, Any]:
        calls["n"] += 1
        return own if calls["n"] == 1 else other

    async def fake_band(engine: Any, embedding: Any, **kwargs: Any) -> list[SearchHit]:
        return [match]

    monkeypatch.setattr(postgres_module, "get_chunk", fake_get_chunk)
    monkeypatch.setattr(search_module, "similarity_band_chunks", fake_band)

    checked, written = await cross_doc_module._discover_for_chunk(
        None, None, _no_generate, own_doc_id=str(own["doc_id"]), chunk_id=str(own["chunk_id"])
    )

    assert (checked, written) == (False, 0)


async def test_match_con_entidades_de_ambos_lados_escribe_relacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    own = _chunk(entity_node_ids=["node-a"])
    match = _match_hit()
    other = _chunk(chunk_id=match.chunk_id, doc_id=match.doc_id, entity_node_ids=["node-b"])

    calls = {"n": 0}

    async def fake_get_chunk(engine: Any, chunk_id: Any) -> dict[str, Any]:
        calls["n"] += 1
        return own if calls["n"] == 1 else other

    async def fake_band(engine: Any, embedding: Any, **kwargs: Any) -> list[SearchHit]:
        return [match]

    async def fake_fetch_nodes(driver: Any, node_ids: list[str]) -> list[dict[str, Any]]:
        assert sorted(node_ids) == ["node-a", "node-b"]
        return [
            {"id": "node-a", "canonical_name": "fastapi", "name": "FastAPI"},
            {"id": "node-b", "canonical_name": "pydantic", "name": "Pydantic"},
        ]

    merged: list[dict[str, Any]] = []

    async def fake_merge_relation(driver: Any, **kwargs: Any) -> None:
        merged.append(kwargs)

    async def generate(prompt: str) -> str:
        return (
            '[{"source": "FastAPI", "relation": "USES", "target": "Pydantic", "confidence": 0.8}]'
        )

    monkeypatch.setattr(postgres_module, "get_chunk", fake_get_chunk)
    monkeypatch.setattr(search_module, "similarity_band_chunks", fake_band)
    monkeypatch.setattr(neo4j_module, "fetch_nodes_by_ids", fake_fetch_nodes)
    monkeypatch.setattr(neo4j_module, "merge_relation", fake_merge_relation)

    checked, written = await cross_doc_module._discover_for_chunk(
        None, None, generate, own_doc_id=str(own["doc_id"]), chunk_id=str(own["chunk_id"])
    )

    assert (checked, written) == (True, 1)
    assert merged[0]["source_id"] == "node-a"
    assert merged[0]["target_id"] == "node-b"
    assert merged[0]["relation_type"] == "USES"
    assert sorted(merged[0]["sources"]) == sorted({str(own["doc_id"]), str(other["doc_id"])})


async def test_relacion_con_entidad_desconocida_se_descarta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    own = _chunk(entity_node_ids=["node-a"])
    match = _match_hit()
    other = _chunk(chunk_id=match.chunk_id, doc_id=match.doc_id, entity_node_ids=["node-b"])

    calls = {"n": 0}

    async def fake_get_chunk(engine: Any, chunk_id: Any) -> dict[str, Any]:
        calls["n"] += 1
        return own if calls["n"] == 1 else other

    async def fake_band(engine: Any, embedding: Any, **kwargs: Any) -> list[SearchHit]:
        return [match]

    async def fake_fetch_nodes(driver: Any, node_ids: list[str]) -> list[dict[str, Any]]:
        return [
            {"id": "node-a", "canonical_name": "fastapi", "name": "FastAPI"},
            {"id": "node-b", "canonical_name": "pydantic", "name": "Pydantic"},
        ]

    async def unreachable_merge(driver: Any, **kwargs: Any) -> None:
        raise AssertionError("no debe mergear una relación con entidad desconocida")

    async def generate(prompt: str) -> str:
        # "Django" no está en entity_names — s8 ya lo descarta en el parseo.
        return '[{"source": "Django", "relation": "USES", "target": "Pydantic", "confidence": 0.8}]'

    monkeypatch.setattr(postgres_module, "get_chunk", fake_get_chunk)
    monkeypatch.setattr(search_module, "similarity_band_chunks", fake_band)
    monkeypatch.setattr(neo4j_module, "fetch_nodes_by_ids", fake_fetch_nodes)
    monkeypatch.setattr(neo4j_module, "merge_relation", unreachable_merge)

    checked, written = await cross_doc_module._discover_for_chunk(
        None, None, generate, own_doc_id=str(own["doc_id"]), chunk_id=str(own["chunk_id"])
    )

    assert (checked, written) == (True, 0)


async def test_async_discover_respeta_el_tope_de_chunks_por_corrida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    async def fake_discover_for_chunk(
        engine: Any, driver: Any, generate: Any, *, own_doc_id: str, chunk_id: str
    ) -> tuple[bool, int]:
        seen.append(chunk_id)
        return True, 0

    class _NoopLLM:
        async def generate(self, prompt: str, *, system: str | None = None) -> str:
            return "[]"

        async def aclose(self) -> None:
            pass

    class _NoopDriver:
        async def close(self) -> None:
            pass

    class _NoopEngine:
        async def dispose(self) -> None:
            pass

    monkeypatch.setattr(cross_doc_module, "_discover_for_chunk", fake_discover_for_chunk)
    monkeypatch.setattr(cross_doc_module, "create_engine", lambda settings: _NoopEngine())
    monkeypatch.setattr(neo4j_module, "create_driver", lambda settings: _NoopDriver())
    monkeypatch.setattr(cross_doc_module, "OllamaLLMClient", lambda settings: _NoopLLM())

    many_chunk_ids = [str(uuid.uuid4()) for _ in range(cross_doc_module.MAX_CHUNKS_PER_RUN + 5)]

    result = await cross_doc_module._async_discover_cross_document_relations(
        doc_id="doc-1", chunk_ids=many_chunk_ids
    )

    assert len(seen) == cross_doc_module.MAX_CHUNKS_PER_RUN
    assert result["chunks_checked"] == cross_doc_module.MAX_CHUNKS_PER_RUN


def test_la_task_esta_registrada_con_nombre_de_evento() -> None:
    assert "kos.discover_cross_document_relations" in app.tasks
