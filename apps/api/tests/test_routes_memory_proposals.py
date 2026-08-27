"""Tests de /v1/memory/proposals sin infra real (storage/embedder mockeados) —
mitigación del riesgo documentado en docs/deuda-tecnica.md: un `memory.store`
sin `confirm=true` queda pendiente de aprobación humana, nunca se pierde ni se
auto-aprueba."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Sequence

import pytest
from fastapi.testclient import TestClient

import kos_api.main as kos_api_main
from kos_api.main import create_app
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage

_NOW = datetime.now(UTC)


class _FakeEmbedder:
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[0.0] * 4 for _ in texts]

    async def aclose(self) -> None:
        return None


def _proposal(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "proposal_id": uuid.uuid4(),
        "query": "¿qué es KOS?",
        "answer": "un motor de conocimiento",
        "sources": ["doc-a"],
        "confidence": 0.8,
        "status": "pending",
        "rejected_reason": None,
        "memory_id": None,
        "trace_id": "trace-1",
        "created_at": _NOW,
        "resolved_at": None,
    }
    base.update(overrides)
    return base


def test_list_proposals_devuelve_pagina(monkeypatch: pytest.MonkeyPatch) -> None:
    item = _proposal()

    async def fake_list(
        engine: Any, *, status: str | None, cursor: uuid.UUID | None, limit: int
    ) -> tuple[list[dict[str, Any]], uuid.UUID | None]:
        assert status is None
        return [item], None

    monkeypatch.setattr(postgres_storage, "list_memory_proposals", fake_list)
    with TestClient(create_app()) as client:
        response = client.get("/v1/memory/proposals")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["proposal_id"] == str(item["proposal_id"])
    assert body["items"][0]["status"] == "pending"


def test_patch_proposal_rechaza(monkeypatch: pytest.MonkeyPatch) -> None:
    item = _proposal(status="rejected", rejected_reason="ya lo sabía")

    async def fake_update(
        engine: Any,
        proposal_id: uuid.UUID,
        *,
        status: str,
        rejected_reason: str | None = None,
        memory_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        assert status == "rejected"
        assert rejected_reason == "ya lo sabía"
        return item

    monkeypatch.setattr(postgres_storage, "update_memory_proposal_status", fake_update)
    with TestClient(create_app()) as client:
        response = client.patch(
            f"/v1/memory/proposals/{item['proposal_id']}",
            json={"status": "rejected", "reason": "ya lo sabía"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_patch_proposal_aprueba_escribe_memoria_de_verdad(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aprobar reusa `memory.store` con confirm=True (único punto de entrada
    de escritura) — no debe llamarse `insert_memory_proposal` de nuevo, y el
    `memory_id` real queda guardado en la propuesta."""
    item = _proposal()
    inserted_memories: list[dict[str, Any]] = []
    updated: dict[str, Any] = {}

    async def fake_get(engine: Any, proposal_id: uuid.UUID) -> dict[str, Any]:
        return item

    async def fake_insert_memory(engine: Any, **kwargs: Any) -> None:
        inserted_memories.append(kwargs)

    async def fake_find_node_ids(driver: Any, doc_ids: list[str]) -> list[str]:
        return ["node-1"]

    async def fake_update(
        engine: Any,
        proposal_id: uuid.UUID,
        *,
        status: str,
        rejected_reason: str | None = None,
        memory_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        updated.update({"status": status, "memory_id": memory_id})
        return {**item, "status": status, "memory_id": memory_id}

    monkeypatch.setattr(kos_api_main, "OllamaEmbeddingClient", lambda settings: _FakeEmbedder())
    monkeypatch.setattr(postgres_storage, "get_memory_proposal", fake_get)
    monkeypatch.setattr(postgres_storage, "insert_memory", fake_insert_memory)
    monkeypatch.setattr(neo4j_storage, "find_node_ids_by_sources", fake_find_node_ids)
    monkeypatch.setattr(postgres_storage, "update_memory_proposal_status", fake_update)

    with TestClient(create_app()) as client:
        response = client.patch(
            f"/v1/memory/proposals/{item['proposal_id']}", json={"status": "approved"}
        )

    assert response.status_code == 200
    assert len(inserted_memories) == 1
    assert updated["status"] == "approved"
    assert updated["memory_id"] is not None


def test_patch_proposal_404_si_no_existe_o_ya_resuelta(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_update(
        engine: Any,
        proposal_id: uuid.UUID,
        *,
        status: str,
        rejected_reason: str | None = None,
        memory_id: uuid.UUID | None = None,
    ) -> None:
        return None

    monkeypatch.setattr(postgres_storage, "update_memory_proposal_status", fake_update)
    with TestClient(create_app()) as client:
        response = client.patch(
            f"/v1/memory/proposals/{uuid.uuid4()}", json={"status": "rejected"}
        )

    assert response.status_code == 404


def test_patch_proposal_status_invalido_es_422() -> None:
    with TestClient(create_app()) as client:
        response = client.patch(
            f"/v1/memory/proposals/{uuid.uuid4()}", json={"status": "pending"}
        )
    assert response.status_code == 422
