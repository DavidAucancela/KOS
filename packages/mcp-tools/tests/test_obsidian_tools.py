"""Tests unitarios de `kos_mcp.tools.obsidian` (Sprint 20, deuda cerrada):
`kos_core.notes` mockeado, vault falso en un directorio temporal."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from kos_core.config import Settings
from kos_mcp.tools import obsidian as obsidian_tools


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    templates = tmp_path / "_Templates"
    templates.mkdir()
    (templates / "Concepto.md").write_text(
        '---\ntitle: "<% tp.file.title %>"\n---\n\n# <% tp.file.title %>\n', encoding="utf-8"
    )
    return tmp_path


async def test_sin_confirm_no_escribe(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        raise AssertionError("no debe resolver el vault sin confirm=True")

    monkeypatch.setattr(obsidian_tools, "get_vault_path", fake_get_vault_path)

    result = await obsidian_tools._create_note_core(
        None,
        Settings(),
        template_name="Concepto",
        folder="Ideas",
        title="Docker",
        source_name="vault-real",
        confirm=False,
        trace_id="trace-1",
    )

    assert result.approved is False
    assert result.path is None
    assert "confirm=true" in result.message
    assert not (vault / "Ideas" / "Docker.md").exists()


async def test_con_confirm_crea_la_nota(vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        assert source_name == "vault-real"
        return vault

    monkeypatch.setattr(obsidian_tools, "get_vault_path", fake_get_vault_path)

    result = await obsidian_tools._create_note_core(
        None,
        Settings(),
        template_name="Concepto",
        folder="Ideas",
        title="Docker",
        source_name="vault-real",
        confirm=True,
        trace_id="trace-1",
    )

    assert result.approved is True
    assert result.path == str(vault / "Ideas" / "Docker.md")
    assert "# Docker" in Path(result.path).read_text(encoding="utf-8")


async def test_source_name_por_defecto_usa_settings(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        assert source_name == "vault-real"
        return vault

    monkeypatch.setattr(obsidian_tools, "get_vault_path", fake_get_vault_path)

    result = await obsidian_tools._create_note_core(
        None,
        Settings(kos_default_vault_source="vault-real"),
        template_name="Concepto",
        folder="Ideas",
        title="Docker",
        source_name=None,
        confirm=True,
        trace_id="trace-1",
    )

    assert result.approved is True


@pytest.fixture
def _patched_vault(vault: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        return vault

    monkeypatch.setattr(obsidian_tools, "get_vault_path", fake_get_vault_path)
    return vault


async def test_read_note_sin_confirm_no_resuelve(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        raise AssertionError("no debe resolver el vault sin confirm=True")

    monkeypatch.setattr(obsidian_tools, "get_vault_path", fake_get_vault_path)

    result = await obsidian_tools._read_note_core(
        None, Settings(), path="Nota.md", source_name="v", confirm=False, trace_id="t"
    )

    assert result.approved is False
    assert result.content is None
    assert "confirm=true" in result.message


async def test_read_note_con_confirm_devuelve_contenido(_patched_vault: Path) -> None:
    (_patched_vault / "Nota.md").write_text("cuerpo", encoding="utf-8")

    result = await obsidian_tools._read_note_core(
        None, Settings(), path="Nota.md", source_name="v", confirm=True, trace_id="t"
    )

    assert result.approved is True
    assert result.content == "cuerpo"


async def test_update_note_sin_confirm_no_escribe(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (vault / "Nota.md").write_text("viejo", encoding="utf-8")

    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        raise AssertionError("no debe resolver el vault sin confirm=True")

    monkeypatch.setattr(obsidian_tools, "get_vault_path", fake_get_vault_path)

    result = await obsidian_tools._update_note_core(
        None, Settings(), path="Nota.md", content="nuevo", source_name="v", confirm=False,
        trace_id="t",
    )

    assert result.approved is False
    assert "confirm=true" in result.message
    assert (vault / "Nota.md").read_text(encoding="utf-8") == "viejo"


async def test_update_note_con_confirm_sobreescribe(_patched_vault: Path) -> None:
    (_patched_vault / "Nota.md").write_text("viejo", encoding="utf-8")

    result = await obsidian_tools._update_note_core(
        None, Settings(), path="Nota.md", content="nuevo", source_name="v", confirm=True,
        trace_id="t",
    )

    assert result.approved is True
    assert result.path == str(_patched_vault / "Nota.md")
    assert (_patched_vault / "Nota.md").read_text(encoding="utf-8") == "nuevo"


async def test_update_note_inexistente_reporta_y_no_crea(_patched_vault: Path) -> None:
    result = await obsidian_tools._update_note_core(
        None, Settings(), path="NoExiste.md", content="x", source_name="v", confirm=True,
        trace_id="t",
    )

    assert result.approved is True
    assert result.path is None
    assert "no encontrada" in result.message
    assert not (_patched_vault / "NoExiste.md").exists()


async def test_create_folder_sin_confirm_no_crea(
    vault: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get_vault_path(engine: Any, source_name: str) -> Path:
        raise AssertionError("no debe resolver el vault sin confirm=True")

    monkeypatch.setattr(obsidian_tools, "get_vault_path", fake_get_vault_path)

    result = await obsidian_tools._create_folder_core(
        None, Settings(), path="Ideas/Sub", source_name="v", confirm=False, trace_id="t"
    )

    assert result.approved is False
    assert "confirm=true" in result.message
    assert not (vault / "Ideas" / "Sub").exists()


async def test_create_folder_con_confirm_crea(_patched_vault: Path) -> None:
    result = await obsidian_tools._create_folder_core(
        None, Settings(), path="Ideas/Sub", source_name="v", confirm=True, trace_id="t"
    )

    assert result.approved is True
    assert (_patched_vault / "Ideas" / "Sub").is_dir()
