"""Tests de POST /v1/query sin infraestructura (búsqueda y LLM mockeados)."""

import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kos_api import main as kos_api_main
from kos_api.main import create_app
from kos_api.services import memory_service, notes_service
from kos_core.storage import search as search_storage
from kos_core.storage.search import SearchHit


@pytest.fixture(autouse=True)
def _no_real_memory_enqueue(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """`enqueue_learn` intentaría una conexión real a Redis (Sprint 12); se
    captura en una lista en vez de mockear un cliente Celery completo."""
    calls: list[dict[str, Any]] = []

    def fake_enqueue(settings: Any, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(memory_service, "enqueue_learn", fake_enqueue)
    return calls


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


_FIXED_PLAN_JSON = (
    '[{"id": "s1", "agent": "retrieval", "task": "buscar", "inputs": {}, "depends_on": []},'
    ' {"id": "s2", "agent": "writing", "task": "redactar", "inputs": {}, "depends_on": ["s1"]}]'
)


class _EchoLLM:
    """Ecoa el contexto recibido: permite verificar que la síntesis lo consume.

    Sprint 18: el mismo cliente sirve tanto al Planner (pide el plan en JSON)
    como a `WritingAgent` (síntesis) — se distingue por el `system` prompt.
    `calls` cuenta solo las llamadas de síntesis, para no romper el sentido
    original de estas aserciones ("el LLM no se llama para alucinar")."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        if system is not None and "planner de KOS" in system:
            return _FIXED_PLAN_JSON
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
        engine: Any, query: str, query_embedding: Sequence[float], *, limit: int = 10, **kwargs: Any
    ) -> list[SearchHit]:
        return [hit]

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)
    llm = _EchoLLM()
    monkeypatch.setattr(kos_api_main, "OllamaEmbeddingClient", lambda settings: _FakeEmbedder())
    with TestClient(create_app()) as client:
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
    assert uuid.UUID(body["plan_id"])


def test_respuesta_exitosa_encola_memoria_episodica(
    monkeypatch: pytest.MonkeyPatch, _no_real_memory_enqueue: list[dict[str, Any]]
) -> None:
    hit = _hit()

    async def fake_hybrid(
        engine: Any, query: str, query_embedding: Sequence[float], *, limit: int = 10, **kwargs: Any
    ) -> list[SearchHit]:
        return [hit]

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)
    monkeypatch.setattr(kos_api_main, "OllamaEmbeddingClient", lambda settings: _FakeEmbedder())
    with TestClient(create_app()) as client:
        client.app.state.llm_client = _EchoLLM()
        response = client.post("/v1/query", json={"query": "¿qué es KOS?"})

    assert response.status_code == 200
    [call] = _no_real_memory_enqueue
    assert call["query"] == "¿qué es KOS?"
    assert call["sources"] == [str(hit.doc_id)]
    assert call["confidence"] == response.json()["confidence"]


def test_comando_no_encola_memoria(
    monkeypatch: pytest.MonkeyPatch, _no_real_memory_enqueue: list[dict[str, Any]]
) -> None:
    """Un comando (`/nueva-maquina`) es una acción, no una pregunta — no genera
    memoria episódica (doc 04 §3 paso 1 habla de interacciones de consulta)."""

    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        return Path("/vault-falso")

    monkeypatch.setattr(notes_service, "get_vault_path", fake_get_vault_path)
    monkeypatch.setattr(notes_service, "create_note", lambda vault_path, **kwargs: Path("x.md"))

    monkeypatch.setattr(kos_api_main, "OllamaEmbeddingClient", lambda settings: _FakeEmbedder())
    with TestClient(create_app()) as client:
        client.app.state.llm_client = _EchoLLM()
        response = client.post("/v1/query", json={"query": "/nueva-maquina Fawn"})

    assert response.status_code == 200
    assert _no_real_memory_enqueue == []


def test_sin_hits_no_alucina(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_hybrid(
        engine: Any, query: str, query_embedding: Sequence[float], *, limit: int = 10, **kwargs: Any
    ) -> list[SearchHit]:
        return []

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)
    llm = _EchoLLM()
    monkeypatch.setattr(kos_api_main, "OllamaEmbeddingClient", lambda settings: _FakeEmbedder())
    with TestClient(create_app()) as client:
        client.app.state.llm_client = llm
        response = client.post("/v1/query", json={"query": "algo que no existe"})

    assert response.status_code == 200
    body = response.json()
    assert body["evidence"] == []
    assert body["confidence"] == 0.0
    assert llm.calls == 0, "sin evidencia no se llama al LLM (no alucinar)"
    assert "no encontré" in body["answer"].lower()


def test_hybrid_degrada_a_lexica_si_falla_el_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_lexical(
        engine: Any, query: str, *, limit: int = 20, **kwargs: Any
    ) -> list[SearchHit]:
        return [_hit(source="lexical")]

    monkeypatch.setattr(search_storage, "lexical_search", fake_lexical)
    monkeypatch.setattr(kos_api_main, "OllamaEmbeddingClient", lambda settings: _FailingEmbedder())
    with TestClient(create_app()) as client:
        client.app.state.llm_client = _EchoLLM()
        response = client.post("/v1/query", json={"query": "¿qué es KOS?"})

    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    assert body["evidence"], "la degradación a léxica debe seguir aportando evidencia"


def test_llm_caido_con_hits_es_503(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_hybrid(
        engine: Any, query: str, query_embedding: Sequence[float], *, limit: int = 10, **kwargs: Any
    ) -> list[SearchHit]:
        return [_hit()]

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)
    monkeypatch.setattr(kos_api_main, "OllamaEmbeddingClient", lambda settings: _FakeEmbedder())
    with TestClient(create_app()) as client:
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
    monkeypatch.setattr(kos_api_main, "OllamaEmbeddingClient", lambda settings: _FakeEmbedder())
    with TestClient(create_app()) as client:
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
            "inputs": {},
            "depends_on": [],
            "evidence_count": None,
            "confidence": None,
            "cost": None,
        }
    ]
    assert llm.calls == 0, "el comando no debe pasar por retrieval/síntesis"
    assert creadas == [
        {"template_name": "MaquinaHTB", "folder": "Security/HackTheBox/Máquinas", "title": "Fawn"}
    ]


def test_comando_crear_nota_generico_crea_nota_sin_llamar_al_llm(
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
    monkeypatch.setattr(kos_api_main, "OllamaEmbeddingClient", lambda settings: _FakeEmbedder())
    with TestClient(create_app()) as client:
        client.app.state.llm_client = llm
        response = client.post(
            "/v1/query", json={"query": "/crear-nota Proyecto | Proyectos | Tuti"}
        )

    assert response.status_code == 200
    body = response.json()
    assert "Tuti.md" in body["answer"]
    assert body["evidence"] == []
    assert llm.calls == 0, "el comando no debe pasar por retrieval/síntesis"
    assert creadas == [{"template_name": "Proyecto", "folder": "Proyectos", "title": "Tuti"}]


def test_comando_crear_nota_mal_formado_cae_al_pipeline_normal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_hybrid(
        engine: Any, query: str, query_embedding: Sequence[float], *, limit: int = 10, **kwargs: Any
    ) -> list[SearchHit]:
        return []

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)
    monkeypatch.setattr(kos_api_main, "OllamaEmbeddingClient", lambda settings: _FakeEmbedder())
    with TestClient(create_app()) as client:
        client.app.state.llm_client = _EchoLLM()
        response = client.post("/v1/query", json={"query": "/crear-nota Proyecto | Proyectos"})

    assert response.status_code == 200
    body = response.json()
    assert "no encontré" in body["answer"].lower()


def test_pregunta_por_plantilla_no_fabrica_responde_sin_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hit = _hit(
        source_id="_Templates/Proyecto.md",
        title="<% tp.file.title %>",
        doc_type="template",
        score=2.0 / (search_storage.RRF_K + 1) * 0.9,
    )

    async def fake_hybrid(*args: Any, **kwargs: Any) -> list[SearchHit]:
        assert kwargs.get("doc_type") == "template"
        return [hit]

    monkeypatch.setattr(search_storage, "hybrid_search", fake_hybrid)
    llm = _EchoLLM()
    monkeypatch.setattr(kos_api_main, "OllamaEmbeddingClient", lambda settings: _FakeEmbedder())
    with TestClient(create_app()) as client:
        client.app.state.llm_client = llm
        response = client.post(
            "/v1/query",
            json={
                "query": "quiero crear información para describir un proyecto, "
                "¿qué plantilla me sirve?"
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert llm.calls == 0, "la rama s0 no debe pasar por síntesis LLM"
    assert body["plan"] == [
        {
            "id": "s0",
            "agent": "intent",
            "task": "detectar intención de creación de nota",
            "inputs": {},
            "depends_on": [],
            "evidence_count": None,
            "confidence": None,
            "cost": None,
        }
    ]
    [ev] = body["evidence"]
    assert ev["source_id"] == "_Templates/Proyecto.md"
    assert "/crear-nota Proyecto" in body["answer"]


def test_comando_nueva_maquina_nota_existente_responde_conflicto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        return Path("/vault-falso")

    def fake_create_note(vault_path: Path, **kwargs: Any) -> Path:
        raise notes_service.NoteAlreadyExistsError("Ya existe una nota en: /vault-falso/x/Fawn.md")

    monkeypatch.setattr(notes_service, "get_vault_path", fake_get_vault_path)
    monkeypatch.setattr(notes_service, "create_note", fake_create_note)

    monkeypatch.setattr(kos_api_main, "OllamaEmbeddingClient", lambda settings: _FakeEmbedder())
    with TestClient(create_app()) as client:
        client.app.state.llm_client = _EchoLLM()
        response = client.post("/v1/query", json={"query": "/nueva-maquina Fawn"})

    assert response.status_code == 200
    body = response.json()
    assert "Ya existe" in body["answer"]
