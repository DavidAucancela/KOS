"""Tests de /v1/recommendations sin Postgres real (storage mockeado, doc 06 §2,
doc 11, Sprint 23)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kos_api.main import create_app
from kos_core.storage import postgres as postgres_storage

_NOW = datetime.now(UTC)


def _recommendation(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "recommendation_id": uuid.uuid4(),
        "type": "gap",
        "title": "Posible laguna: Docker",
        "description": "Docker es prerrequisito de Kubernetes pero está poco evidenciado",
        "evidence": [],
        "target_entities": ["node-1"],
        "confidence": 0.7,
        "priority": 1,
        "status": "pending",
        "dismissed_reason": None,
        "source_event_id": "trace-1",
        "created_at": _NOW,
        "resolved_at": None,
    }
    base.update(overrides)
    return base


def test_list_recommendations_devuelve_pagina(monkeypatch: pytest.MonkeyPatch) -> None:
    item = _recommendation()

    async def fake_list(
        engine: Any, *, type: str | None, status: str | None, cursor: uuid.UUID | None, limit: int
    ) -> tuple[list[dict[str, Any]], uuid.UUID | None]:
        assert type is None
        assert status is None
        return [item], None

    monkeypatch.setattr(postgres_storage, "list_recommendations", fake_list)
    with TestClient(create_app()) as client:
        response = client.get("/v1/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["recommendation_id"] == str(item["recommendation_id"])
    assert body["items"][0]["type"] == "gap"
    assert body["next_cursor"] is None


def test_list_recommendations_filtra_por_type_y_status(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_list(
        engine: Any, *, type: str | None, status: str | None, cursor: uuid.UUID | None, limit: int
    ) -> tuple[list[dict[str, Any]], uuid.UUID | None]:
        captured.update({"type": type, "status": status, "limit": limit})
        return [], None

    monkeypatch.setattr(postgres_storage, "list_recommendations", fake_list)
    with TestClient(create_app()) as client:
        response = client.get("/v1/recommendations", params={"type": "gap", "status": "pending"})

    assert response.status_code == 200
    assert captured == {"type": "gap", "status": "pending", "limit": 20}


def test_list_recommendations_tipo_invalido_es_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/v1/recommendations", params={"type": "no-existe"})
    assert response.status_code == 422


def test_list_recommendations_status_invalido_es_422() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/v1/recommendations", params={"status": "no-existe"})
    assert response.status_code == 422
