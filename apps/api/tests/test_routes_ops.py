"""/v1/ops/status: visibilidad del cron del despliegue gestionado (ADR-0009)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kos_api.main import create_app
from kos_core.config import Settings


def _client(monkeypatch: pytest.MonkeyPatch, row: dict[str, Any] | None, **over: Any) -> TestClient:
    async def fake_last_cron_run(engine: Any, *, job: str = "drain") -> dict[str, Any] | None:
        return row

    monkeypatch.setattr("kos_core.storage.postgres.last_cron_run", fake_last_cron_run, raising=True)
    monkeypatch.setattr("kos_api.routes.ops.postgres_storage.last_cron_run", fake_last_cron_run)
    monkeypatch.setattr("kos_api.deps.get_settings", lambda: Settings(_env_file=None, **over))
    return TestClient(create_app())


def _run(hours_ago: float, status: str = "ok") -> dict[str, Any]:
    finished = datetime.now(UTC) - timedelta(hours=hours_ago)
    return {
        "run_id": uuid.uuid4(),
        "job": "drain",
        "started_at": finished - timedelta(minutes=3),
        "finished_at": finished,
        "status": status,
        "tasks_drained": 7,
        "detail": None,
    }


def test_ejecucion_reciente_no_esta_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(monkeypatch, _run(2)) as client:
        body = client.get("/v1/ops/status").json()
    assert body["ingesta"]["stale"] is False
    assert body["ingesta"]["last_run"]["tasks_drained"] == 7
    assert body["ingesta"]["hours_since_last_run"] == pytest.approx(2, abs=0.1)


def test_ejecucion_vieja_esta_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con el cron 2x/día, pasar de 18h significa que se saltó una ejecución."""
    with _client(monkeypatch, _run(20)) as client:
        body = client.get("/v1/ops/status").json()
    assert body["ingesta"]["stale"] is True
    assert body["ingesta"]["stale_after_hours"] == 18


def test_sin_ninguna_ejecucion_esta_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Que el cron no haya corrido nunca es exactamente el fallo a detectar."""
    with _client(monkeypatch, None) as client:
        body = client.get("/v1/ops/status").json()
    assert body["ingesta"]["stale"] is True
    assert body["ingesta"]["last_run"] is None
    assert body["ingesta"]["hours_since_last_run"] is None


def test_modo_refleja_el_despliegue(monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(monkeypatch, _run(1), kos_serverless_mode=True) as client:
        assert client.get("/v1/ops/status").json()["mode"] == "managed"
    with _client(monkeypatch, _run(1)) as client:
        assert client.get("/v1/ops/status").json()["mode"] == "local"
