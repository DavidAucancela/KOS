"""Tests de POST /v1/query sin infraestructura (búsqueda y LLM mockeados)."""

import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kos_api.main import create_app
from kos_api.services import notes_service
from kos_core.storage import search as search_storage
from kos_core.storage.search import SearchHit


def _hit(**overrides: Any) -> SearchHit:
    base: dict[str, Any] = {
        "chunk_id": uuid.uuid4(),
        "doc_id": uuid.uuid4(),
        "text": "KOS es un motor de conocimiento independiente de fuentes.",
        "score": 0.87,
        "source": "hybrid",
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

    async def aclose(self) -> None:
        return None


class _FailingEmbedder:
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("ollama embeddings caído")

    async def aclose(self) -> None:
        return None


class _EchoLLM:
    """Ecoa el contexto recibido: permite verificar que la síntesis lo consume."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        self.calls += 1
        return f"Respuesta con citas [1]. (prompt visto: {len(prompt)} chars)"

    async def aclose(self) -> None:
        return None


class _FailingLLM:
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("ollama llm caído")

    async def aclose(self) -> None:
        return None


def test_con_hits_devuelve_respuesta_evidencia_y_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    hit = _hit()

    async def fake_hybrid(
        engine: Any, query: str, query_embedding: Sequence[float], *, limit: int = 10
    ) -> list[SearchHit]:
        return [hit]

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)
    llm = _EchoLLM()
    with TestClient(create_app()) as client:
        client.app.state.embedding_client = _FakeEmbedder()
        client.app.state.llm_client = llm
        response = client.post("/v1/query", json={"query": "¿qué es KOS?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"].startswith("Respuesta con citas")
    assert llm.calls == 1
    [ev] = body["evidence"]
    # Evidencia mínima (doc 06 §2): doc_id + chunk_id + quote
    assert ev["doc_id"] == str(hit.doc_id)
    assert ev["chunk_id"] == str(hit.chunk_id)
    assert ev["quote"] == hit.text
    assert [step["id"] for step in body["plan"]] == ["s1", "s2"]
    assert body["plan"][0]["evidence_count"] == 1
    assert body["trace_id"]


def test_sin_hits_no_alucina(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_hybrid(
        engine: Any, query: str, query_embedding: Sequence[float], *, limit: int = 10
    ) -> list[SearchHit]:
        return []

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)
    llm = _EchoLLM()
    with TestClient(create_app()) as client:
        client.app.state.embedding_client = _FakeEmbedder()
        client.app.state.llm_client = llm
        response = client.post("/v1/query", json={"query": "algo que no existe"})

    assert response.status_code == 200
    body = response.json()
    assert body["evidence"] == []
    assert body["confidence"] == 0.0
    assert llm.calls == 0, "sin evidencia no se llama al LLM (no alucinar)"
    assert "no encontré" in body["answer"].lower()


def test_hybrid_degrada_a_lexica_si_falla_el_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_lexical(engine: Any, query: str, *, limit: int = 20) -> list[SearchHit]:
        return [_hit(source="lexical")]

    monkeypatch.setattr(search_storage, "lexical_search", fake_lexical)
    with TestClient(create_app()) as client:
        client.app.state.embedding_client = _FailingEmbedder()
        client.app.state.llm_client = _EchoLLM()
        response = client.post("/v1/query", json={"query": "¿qué es KOS?"})

    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    assert body["evidence"], "la degradación a léxica debe seguir aportando evidencia"


def test_llm_caido_con_hits_es_503(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_hybrid(
        engine: Any, query: str, query_embedding: Sequence[float], *, limit: int = 10
    ) -> list[SearchHit]:
        return [_hit()]

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)
    with TestClient(create_app()) as client:
        client.app.state.embedding_client = _FakeEmbedder()
        client.app.state.llm_client = _FailingLLM()
        response = client.post("/v1/query", json={"query": "¿qué es KOS?"})

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")


def test_query_vacia_es_422() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/v1/query", json={"query": ""})
    assert response.status_code == 422


def test_comando_nueva_maquina_crea_nota_sin_llamar_al_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        return Path("/vault-falso")

    creadas: list[dict[str, Any]] = []

    def fake_create_note(vault_path: Path, **kwargs: Any) -> Path:
        creadas.append(kwargs)
        return vault_path / kwargs["folder"] / f"{kwargs['title']}.md"

    monkeypatch.setattr(notes_service, "get_vault_path", fake_get_vault_path)
    monkeypatch.setattr(notes_service, "create_note", fake_create_note)

    llm = _EchoLLM()
    with TestClient(create_app()) as client:
        client.app.state.embedding_client = _FakeEmbedder()
        client.app.state.llm_client = llm
        response = client.post("/v1/query", json={"query": "/nueva-maquina Fawn"})

    assert response.status_code == 200
    body = response.json()
    assert "Fawn.md" in body["answer"]
    assert body["evidence"] == []
    assert body["plan"] == [
        {
            "id": "s0",
            "agent": "notes",
            "task": "crear nota desde plantilla",
            "depends_on": [],
            "evidence_count": None,
        }
    ]
    assert llm.calls == 0, "el comando no debe pasar por retrieval/síntesis"
    assert creadas == [
        {"template_name": "MaquinaHTB", "folder": "Security/HackTheBox/Máquinas", "title": "Fawn"}
    ]


def test_comando_nueva_maquina_nota_existente_responde_conflicto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        return Path("/vault-falso")

    def fake_create_note(vault_path: Path, **kwargs: Any) -> Path:
        raise notes_service.NoteAlreadyExistsError("Ya existe una nota en: /vault-falso/x/Fawn.md")

    monkeypatch.setattr(notes_service, "get_vault_path", fake_get_vault_path)
    monkeypatch.setattr(notes_service, "create_note", fake_create_note)

    with TestClient(create_app()) as client:
        client.app.state.embedding_client = _FakeEmbedder()
        client.app.state.llm_client = _EchoLLM()
        response = client.post("/v1/query", json={"query": "/nueva-maquina Fawn"})

    assert response.status_code == 200
    body = response.json()
    assert "Ya existe" in body["answer"]
