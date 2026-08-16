"""Tests unitarios de `kos_core.notes.create_note` (promovido desde
`apps/api` en Sprint 20): puro filesystem, sin engine — `get_vault_path`/
`list_templates` ya se prueban indirectamente vía `apps/api/tests/test_routes_notes.py`."""

from __future__ import annotations

from pathlib import Path

import pytest

from kos_core.notes import NoteAlreadyExistsError, TemplateNotFoundError, create_note


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    templates = tmp_path / "_Templates"
    templates.mkdir()
    (templates / "Concepto.md").write_text(
        '---\ntitle: "<% tp.file.title %>"\n---\n\n# <% tp.file.title %>\n', encoding="utf-8"
    )
    return tmp_path


def test_create_note_renderiza_y_escribe(vault: Path) -> None:
    path = create_note(vault, template_name="Concepto", folder="Ideas", title="Docker")

    assert path == vault / "Ideas" / "Docker.md"
    assert "# Docker" in path.read_text(encoding="utf-8")


def test_create_note_plantilla_inexistente() -> None:
    with pytest.raises(TemplateNotFoundError):
        create_note(Path("/no/existe"), template_name="Nada", folder="x", title="y")


def test_create_note_no_sobreescribe(vault: Path) -> None:
    (vault / "Docker.md").write_text("ya existe", encoding="utf-8")

    with pytest.raises(NoteAlreadyExistsError):
        create_note(vault, template_name="Concepto", folder=".", title="Docker")
