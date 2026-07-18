"""Test de GET /metrics (doc 09 §6, Sprint 5)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from kos_api.main import create_app


def test_metrics_expone_texto_prometheus() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "kos_http_request_duration_seconds" in response.text
    assert "kos_documents_ingested_total" in response.text
