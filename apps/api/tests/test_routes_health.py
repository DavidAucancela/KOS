"""Tests de GET /health con los checks mockeados (sin infraestructura)."""

from __future__ import annotations

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from kos_api.main import create_app
from kos_api.routes import health

_SERVICES = ["postgres", "neo4j", "redis", "minio", "ollama"]


async def _ok(request: Request) -> None:
    return None


async def _boom(request: Request) -> None:
    raise ConnectionError("conexión rechazada")


def test_health_todo_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "CHECKS", {name: _ok for name in _SERVICES})
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["services"]) == set(_SERVICES)
    assert all(service["status"] == "ok" for service in body["services"].values())
    assert all(service["detail"] is None for service in body["services"].values())


def test_health_degradado_con_detalle(monkeypatch: pytest.MonkeyPatch) -> None:
    checks: dict[str, health.Checker] = {name: _ok for name in _SERVICES}
    checks["neo4j"] = _boom
    monkeypatch.setattr(health, "CHECKS", checks)
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["services"]["neo4j"]["status"] == "error"
    assert "conexión rechazada" in body["services"]["neo4j"]["detail"]
    assert body["services"]["postgres"]["status"] == "ok"


def test_health_devuelve_trace_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "CHECKS", {name: _ok for name in _SERVICES})
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.headers["X-Trace-Id"]


def test_health_no_sondea_ollama_en_despliegue_gestionado() -> None:
    """En Railway no hay Ollama (doc 14 §2.1): sondearlo dejaría /health en
    `degraded` para siempre y el aviso perdería su valor."""
    from kos_api.routes.health import _active_checks
    from kos_core.config import Settings

    gestionado = Settings(
        _env_file=None, kos_serverless_mode=True, kos_embedding_provider="openai_compatible"
    )
    assert "ollama" not in _active_checks(gestionado)
    assert "postgres" in _active_checks(gestionado)
    assert "ollama" in _active_checks(Settings(_env_file=None))
