"""Test de GET /metrics (doc 09 §6, Sprint 5)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kos_api.main import create_app
from kos_core.storage import postgres as postgres_storage


def test_metrics_expone_texto_prometheus() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "kos_http_request_duration_seconds" in response.text
    assert "kos_documents_ingested_total" in response.text


def _snapshot() -> dict[str, Any]:
    return {
        "plans": {
            "24h": {
                "summary": {"total": 4, "degraded": 1, "avg_ms": 850.0},
                "degradation": [{"degraded_reason": "step_failure", "count": 1}],
                "agents": [{"agent": "retrieval", "count": 4}, {"agent": "writing", "count": 3}],
                "agent_latency": [{"agent": "writing", "avg_ms": 2500.0, "count": 3}],
            },
            "7d": {
                "summary": {"total": 0, "degraded": 0, "avg_ms": 0.0},
                "degradation": [],
                "agents": [],
                "agent_latency": [],
            },
        },
        "recommender": {
            "runs": {
                "7d": [{"status": "ok", "count": 2}, {"status": "error", "count": 1}],
                "30d": [{"status": "ok", "count": 5}],
            },
            "last_run_at": datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
        },
        "recommendations": {
            "by_group": [
                {"type": "gap", "status": "pending", "count": 20},
                {"type": "gap", "status": "accepted", "count": 1},
            ],
            "created": {"7d": 3, "30d": 21},
            "last_created_at": datetime(2026, 9, 14, 3, 59, tzinfo=UTC),
        },
    }


def test_metrics_incluye_metricas_de_negocio_desde_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_snapshot(engine: Any) -> dict[str, Any]:
        return _snapshot()

    monkeypatch.setattr(postgres_storage, "business_metrics_snapshot", fake_snapshot)
    with TestClient(create_app()) as client:
        text = client.get("/metrics").text

    assert "kos_business_metrics_up 1.0" in text
    assert 'kos_plans{window="24h"} 4.0' in text
    assert 'kos_plans_degraded{reason="step_failure",window="24h"} 1.0' in text
    assert 'kos_plan_agent_steps{agent="retrieval",window="24h"} 4.0' in text
    assert 'kos_plan_agent_latency_avg_ms{agent="writing",window="24h"} 2500.0' in text
    assert 'kos_recommendations{status="pending",type="gap"} 20.0' in text
    assert 'kos_recommendations_created{window="7d"} 3.0' in text
    assert 'kos_recommender_runs{status="ok",window="7d"} 2.0' in text
    assert 'kos_recommender_runs{status="error",window="7d"} 1.0' in text
    assert 'kos_recommender_runs{status="ok",window="30d"} 5.0' in text
    [run_line] = [
        row
        for row in text.splitlines()
        if row.startswith("kos_recommender_last_run_timestamp_seconds ")
    ]
    assert float(run_line.split()[1]) == datetime(2026, 9, 20, 12, 0, tzinfo=UTC).timestamp()
    [line] = [
        row
        for row in text.splitlines()
        if row.startswith("kos_recommendation_last_created_timestamp_seconds ")
    ]
    assert float(line.split()[1]) == datetime(2026, 9, 14, 3, 59, tzinfo=UTC).timestamp()


def test_metrics_no_devuelve_500_si_postgres_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_snapshot(engine: Any) -> dict[str, Any]:
        raise ConnectionError("postgres caído")

    monkeypatch.setattr(postgres_storage, "business_metrics_snapshot", failing_snapshot)
    with TestClient(create_app()) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    # Las métricas de proceso siguen y las de negocio avisan que no hay dato.
    assert "kos_documents_ingested_total" in response.text
    assert "kos_business_metrics_up 0.0" in response.text
    assert "kos_plans{" not in response.text


def test_metrics_no_deja_datos_viejos_tras_una_falla(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    async def flaky_snapshot(engine: Any) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            return _snapshot()
        raise TimeoutError

    monkeypatch.setattr(postgres_storage, "business_metrics_snapshot", flaky_snapshot)
    with TestClient(create_app()) as client:
        assert 'kos_plans{window="24h"} 4.0' in client.get("/metrics").text
        after_failure = client.get("/metrics").text

    assert "kos_business_metrics_up 0.0" in after_failure
    assert "kos_plans{" not in after_failure
    assert "kos_recommendations{" not in after_failure
    assert "kos_recommender_runs{" not in after_failure
    assert "kos_recommender_last_run_timestamp_seconds 0.0" in after_failure
