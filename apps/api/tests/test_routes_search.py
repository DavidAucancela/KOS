"""Tests de POST /v1/search sin infraestructura (búsquedas mockeadas)."""

import uuid
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kos_api.main import create_app
from kos_core.storage import search as search_storage
from kos_core.storage.search import SearchHit


def _hit(**overrides: Any) -> SearchHit:
    base: dict[str, Any] = {
        "chunk_id": uuid.uuid4(),
        "doc_id": uuid.uuid4(),
        "text": "KOS es un motor de conocimiento",
        "score": 0.9,
        "source": "lexical",
        "title": "Proyecto KOS",
        "connector": "obsidian",
        "source_id": "proyectos/Proyecto KOS.md",
        "heading": None,
    }
    base.update(overrides)
    return SearchHit(**base)


class _FakeEmbedder:
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0] * 4 for _ in texts]

    async def aclose(self) -> None:  # el lifespan lo cierra al apagar
        return None


class _FailingEmbedder:
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("ollama caído")

    async def aclose(self) -> None:
        return None


def test_modo_lexical_devuelve_hits_con_evidencia(monkeypatch: pytest.MonkeyPatch) -> None:
    hit = _hit()

    async def fake_lexical(engine: Any, query: str, *, limit: int = 20) -> list[SearchHit]:
        return [hit]

    monkeypatch.setattr(search_storage, "lexical_search", fake_lexical)
    with TestClient(create_app()) as client:
        response = client.post("/v1/search", json={"query": "motor", "mode": "lexical"})

    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is False
    [out] = body["hits"]
    # Evidencia mínima downstream: doc_id + chunk_id + quote (doc 06 §2)
    assert out["doc_id"] == str(hit.doc_id)
    assert out["chunk_id"] == str(hit.chunk_id)
    assert out["quote"] == hit.text


def test_modo_hybrid_usa_la_fusion(monkeypatch: pytest.MonkeyPatch) -> None:
    hit = _hit(source="hybrid", score=0.032)

    async def fake_hybrid(
        engine: Any, query: str, query_embedding: Sequence[float], *, limit: int = 10
    ) -> list[SearchHit]:
        return [hit]

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)
    with TestClient(create_app()) as client:
        client.app.state.embedding_client = _FakeEmbedder()
        response = client.post("/v1/search", json={"query": "motor"})

    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is False
    assert body["hits"][0]["source"] == "hybrid"


def test_hybrid_degrada_a_lexica_si_falla_el_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_lexical(engine: Any, query: str, *, limit: int = 20) -> list[SearchHit]:
        return [_hit()]

    monkeypatch.setattr(search_storage, "lexical_search", fake_lexical)
    with TestClient(create_app()) as client:
        client.app.state.embedding_client = _FailingEmbedder()
        response = client.post("/v1/search", json={"query": "motor"})

    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    assert body["hits"], "la degradación debe seguir devolviendo resultados léxicos"


def test_modo_vector_sin_ollama_es_503_problem_json() -> None:
    with TestClient(create_app()) as client:
        client.app.state.embedding_client = _FailingEmbedder()
        response = client.post("/v1/search", json={"query": "motor", "mode": "vector"})

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")


def test_query_vacia_es_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/search", json={"query": ""})
    assert response.status_code == 422
