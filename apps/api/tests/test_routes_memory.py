"""Tests de /v1/memory sin Postgres real (storage mockeado, doc 06 §2, Sprint 12)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kos_api.main import create_app
from kos_core.storage import postgres as postgres_storage

_NOW = datetime.now(UTC)


def _memory(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "memory_id": uuid.uuid4(),
        "type": "episodic",
        "content": "Preguntó: 'qué es KOS' → un motor de conocimiento",
        "entities": [],
        "sources": [{"doc_id": "doc-a", "confidence": 0.8}],
        "confidence": 0.8,
        "salience": 0.5,
        "created_at": _NOW,
        "last_accessed_at": _NOW,
        "archived_at": None,
        "superseded_by": None,
        "locked": False,
    }
    base.update(overrides)
    return base


def test_list_memories_devuelve_pagina(monkeypatch: pytest.MonkeyPatch) -> None:
    item = _memory()

    async def fake_list(
        engine: Any, *, type: str | None, q: str | None, cursor: uuid.UUID | None, limit: int
    ) -> tuple[list[dict[str, Any]], uuid.UUID | None]:
        assert type is None
        assert q is None
        return [item], None

    monkeypatch.setattr(postgres_storage, "list_memories", fake_list)
    with TestClient(create_app()) as client:
        response = client.get("/v1/memory")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["memory_id"] == str(item["memory_id"])
    assert body["next_cursor"] is None


def test_list_memories_filtra_por_tipo_y_query(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_list(
        engine: Any, *, type: str | None, q: str | None, cursor: uuid.UUID | None, limit: int
    ) -> tuple[list[dict[str, Any]], uuid.UUID | None]:
        captured.update({"type": type, "q": q, "limit": limit})
        return [], None

    monkeypatch.setattr(postgres_storage, "list_memories", fake_list)
    with TestClient(create_app()) as client:
        response = client.get("/v1/memory", params={"type": "semantic", "q": "kubernetes"})

    assert response.status_code == 200
    assert captured == {"type": "semantic", "q": "kubernetes", "limit": 20}


def test_list_memories_tipo_invalido_es_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/v1/memory", params={"type": "no-existe"})
    assert response.status_code == 422


def test_archive_memory_devuelve_204(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_archive(engine: Any, memory_id: uuid.UUID) -> bool:
        return True

    monkeypatch.setattr(postgres_storage, "archive_memory", fake_archive)
    with TestClient(create_app()) as client:
        response = client.delete(f"/v1/memory/{uuid.uuid4()}")

    assert response.status_code == 204


def test_archive_memory_404_si_no_existe_o_ya_archivada(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_archive(engine: Any, memory_id: uuid.UUID) -> bool:
        return False

    monkeypatch.setattr(postgres_storage, "archive_memory", fake_archive)
    with TestClient(create_app()) as client:
        response = client.delete(f"/v1/memory/{uuid.uuid4()}")

    assert response.status_code == 404


def test_correct_memory_devuelve_memoria_locked(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_correct(
        engine: Any,
        memory_id: uuid.UUID,
        *,
        content: str | None,
        type: str | None,
        confidence: float | None,
    ) -> dict[str, Any]:
        captured.update({"content": content, "type": type, "confidence": confidence})
        return _memory(memory_id=memory_id, content=content or "", locked=True, confidence=1.0)

    monkeypatch.setattr(postgres_storage, "correct_memory", fake_correct)
    with TestClient(create_app()) as client:
        response = client.patch(
            f"/v1/memory/{uuid.uuid4()}", json={"content": "texto corregido"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "texto corregido"
    assert body["locked"] is True
    assert captured == {"content": "texto corregido", "type": None, "confidence": None}


def test_correct_memory_404_si_no_existe_o_ya_archivada(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_correct(engine: Any, memory_id: uuid.UUID, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(postgres_storage, "correct_memory", fake_correct)
    with TestClient(create_app()) as client:
        response = client.patch(f"/v1/memory/{uuid.uuid4()}", json={"content": "x"})

    assert response.status_code == 404


def test_correct_memory_confidence_fuera_de_rango_es_422() -> None:
    with TestClient(create_app()) as client:
        response = client.patch(f"/v1/memory/{uuid.uuid4()}", json={"confidence": 1.5})
    assert response.status_code == 422
