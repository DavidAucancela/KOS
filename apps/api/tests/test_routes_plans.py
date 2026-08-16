"""Tests de GET /v1/plans/{id} sin Postgres real (storage mockeado, Sprint 19)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kos_api.main import create_app
from kos_core.storage import postgres as postgres_storage

_NOW = datetime.now(UTC)


def _plan_row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "plan_id": uuid.uuid4(),
        "query": "¿qué es KOS?",
        "steps": [
            {
                "id": "s1",
                "agent": "retrieval",
                "task": "buscar",
                "inputs": {},
                "depends_on": [],
                "evidence_count": 1,
                "confidence": 0.6,
                "cost": {"tokens": 0, "ms": 12.5},
            },
            {
                "id": "s2",
                "agent": "writing",
                "task": "redactar",
                "inputs": {},
                "depends_on": ["s1"],
                "evidence_count": None,
                "confidence": None,
                "cost": None,
            },
        ],
        "degraded": False,
        "degraded_reason": None,
        "elapsed_ms": 42.0,
        "trace_id": "trace-1",
        "created_at": _NOW,
    }
    base.update(overrides)
    return base


def test_get_plan_devuelve_200_con_datos(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _plan_row()

    async def fake_get_plan(engine: Any, plan_id: uuid.UUID) -> dict[str, Any] | None:
        assert plan_id == row["plan_id"]
        return row

    monkeypatch.setattr(postgres_storage, "get_plan", fake_get_plan)
    with TestClient(create_app()) as client:
        response = client.get(f"/v1/plans/{row['plan_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["plan_id"] == str(row["plan_id"])
    assert body["query"] == "¿qué es KOS?"
    assert [s["id"] for s in body["steps"]] == ["s1", "s2"]
    assert body["degraded"] is False
    assert body["degraded_reason"] is None
    assert body["elapsed_ms"] == 42.0
    assert body["trace_id"] == "trace-1"


def test_get_plan_404_si_no_existe(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_plan(engine: Any, plan_id: uuid.UUID) -> dict[str, Any] | None:
        return None

    monkeypatch.setattr(postgres_storage, "get_plan", fake_get_plan)
    with TestClient(create_app()) as client:
        response = client.get(f"/v1/plans/{uuid.uuid4()}")

    assert response.status_code == 404


def test_get_plan_con_degraded_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _plan_row(degraded=True, degraded_reason="budget_timeout")

    async def fake_get_plan(engine: Any, plan_id: uuid.UUID) -> dict[str, Any] | None:
        return row

    monkeypatch.setattr(postgres_storage, "get_plan", fake_get_plan)
    with TestClient(create_app()) as client:
        response = client.get(f"/v1/plans/{row['plan_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    assert body["degraded_reason"] == "budget_timeout"
