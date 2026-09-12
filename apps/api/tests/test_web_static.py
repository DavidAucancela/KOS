"""La API sirve el build de `apps/web` (doc 14 §3): un servicio menos en Railway."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kos_api.main import create_app
from kos_core.config import Settings


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    build = tmp_path / "web-dist"
    (build / "assets").mkdir(parents=True)
    (build / "index.html").write_text("<title>KOS</title>", encoding="utf-8")
    (build / "assets" / "app.js").write_text("console.log('kos')", encoding="utf-8")
    return build


def _app(monkeypatch: pytest.MonkeyPatch, **over: object) -> TestClient:
    monkeypatch.setattr("kos_api.main.get_settings", lambda: Settings(_env_file=None, **over))  # type: ignore[arg-type]
    return TestClient(create_app())


def test_sirve_el_index(monkeypatch: pytest.MonkeyPatch, dist: Path) -> None:
    with _app(monkeypatch, kos_web_dist=str(dist)) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "KOS" in response.text


def test_rutas_del_cliente_devuelven_el_index(monkeypatch: pytest.MonkeyPatch, dist: Path) -> None:
    """Recargar una ruta de React Router no puede dar 404."""
    with _app(monkeypatch, kos_web_dist=str(dist)) as client:
        response = client.get("/memoria/algo")
    assert response.status_code == 200
    assert "KOS" in response.text


def test_los_assets_se_sirven_tal_cual(monkeypatch: pytest.MonkeyPatch, dist: Path) -> None:
    with _app(monkeypatch, kos_web_dist=str(dist)) as client:
        response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_la_api_sigue_ganando_al_catch_all(monkeypatch: pytest.MonkeyPatch, dist: Path) -> None:
    """El montaje va después de los routers: /health no puede caer en el SPA."""
    with _app(monkeypatch, kos_web_dist=str(dist)) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert "services" in response.json()


def test_sin_build_no_monta_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    """En local el web corre en Vite; la API no debe inventarse un SPA."""
    with _app(monkeypatch, kos_web_dist="") as client:
        assert client.get("/ruta-inexistente").status_code == 404


def test_el_html_tambien_pide_credencial(monkeypatch: pytest.MonkeyPatch, dist: Path) -> None:
    """ADR-0010: nada se sirve sin credencial, ni siquiera la web."""
    monkeypatch.setattr(
        "kos_api.middleware.get_settings",
        lambda: Settings(_env_file=None, kos_api_keys="web:k", kos_web_dist=str(dist)),
    )
    with _app(monkeypatch, kos_web_dist=str(dist), kos_api_keys="web:k") as client:
        response = client.get("/")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == 'Basic realm="KOS"'
