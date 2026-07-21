"""Tests de POST /v1/notes con un vault falso en un directorio temporal."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kos_api.main import create_app
from kos_api.services import notes_service


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    templates = tmp_path / "_Templates"
    templates.mkdir()
    (templates / "Concepto.md").write_text(
        '---\ntitle: "<% tp.file.title %>"\n---\n\n# <% tp.file.title %>\n', encoding="utf-8"
    )
    return tmp_path


def test_crea_nota_desde_plantilla(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        return vault

    monkeypatch.setattr(notes_service, "get_vault_path", fake_get_vault_path)

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/notes", json={"template": "Concepto", "folder": "Ideas", "title": "Docker"}
        )

    assert response.status_code == 201
    path = Path(response.json()["path"])
    assert path == vault / "Ideas" / "Docker.md"
    assert "# Docker" in path.read_text(encoding="utf-8")


def test_nota_existente_es_409(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        return vault

    monkeypatch.setattr(notes_service, "get_vault_path", fake_get_vault_path)
    (vault / "Docker.md").write_text("ya existe", encoding="utf-8")

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/notes", json={"template": "Concepto", "folder": ".", "title": "Docker"}
        )

    assert response.status_code == 409


def test_plantilla_inexistente_es_404(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        return vault

    monkeypatch.setattr(notes_service, "get_vault_path", fake_get_vault_path)

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/notes", json={"template": "NoExiste", "folder": "Ideas", "title": "Docker"}
        )

    assert response.status_code == 404


def test_fuente_no_registrada_es_404(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        raise notes_service.VaultSourceNotFoundError(f"Fuente no registrada: {source_name!r}")

    monkeypatch.setattr(notes_service, "get_vault_path", fake_get_vault_path)

    with TestClient(create_app()) as client:
        response = client.post(
            "/v1/notes", json={"template": "Concepto", "folder": "Ideas", "title": "Docker"}
        )

    assert response.status_code == 404
