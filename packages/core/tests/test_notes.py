"""Tests unitarios de `kos_core.notes.create_note` (promovido desde
`apps/api` en Sprint 20): puro filesystem, sin engine — `get_vault_path`/
`list_templates` ya se prueban indirectamente vía `apps/api/tests/test_routes_notes.py`."""

from __future__ import annotations

from pathlib import Path

import pytest

from kos_core.notes import (
    NoteAlreadyExistsError,
    NoteNotFoundError,
    TemplateNotFoundError,
    VaultPathEscapeError,
    create_folder,
    create_note,
    read_note,
    update_note,
)


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


def test_read_note_devuelve_contenido(vault: Path) -> None:
    (vault / "Nota.md").write_text("# Nota\ncuerpo", encoding="utf-8")

    assert read_note(vault, path="Nota.md") == "# Nota\ncuerpo"


def test_read_note_inexistente(vault: Path) -> None:
    with pytest.raises(NoteNotFoundError):
        read_note(vault, path="NoExiste.md")


def test_update_note_sobreescribe(vault: Path) -> None:
    (vault / "Nota.md").write_text("viejo", encoding="utf-8")

    path = update_note(vault, path="Nota.md", content="nuevo")

    assert path == vault / "Nota.md"
    assert path.read_text(encoding="utf-8") == "nuevo"


def test_update_note_inexistente_no_crea(vault: Path) -> None:
    with pytest.raises(NoteNotFoundError):
        update_note(vault, path="NoExiste.md", content="x")
    assert not (vault / "NoExiste.md").exists()


def test_create_folder_anidado_e_idempotente(vault: Path) -> None:
    path = create_folder(vault, path="Ideas/Subtema")

    assert path == vault / "Ideas" / "Subtema"
    assert path.is_dir()
    create_folder(vault, path="Ideas/Subtema")  # no levanta


@pytest.mark.parametrize("fn", [read_note, update_note, create_folder])
def test_rechaza_ruta_que_escapa_del_vault(vault: Path, fn: object) -> None:
    kwargs = {"content": "x"} if fn is update_note else {}
    with pytest.raises(VaultPathEscapeError):
        fn(vault, path="../fuera.md", **kwargs)  # type: ignore[operator]
