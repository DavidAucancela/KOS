"""Cola de escrituras al vault: la API encola, el drain materializa (doc 14 §5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from kos_core.config import Settings
from kos_core.notes import (
    create_folder_or_enqueue,
    create_note_or_enqueue,
    update_note_or_enqueue,
)


class _FakeConn:
    """Recoge lo insertado sin tocar Postgres: aquí se prueba la decisión de
    encolar, no el SQL."""

    def __init__(self, sink: list[Any]) -> None:
        self._sink = sink

    async def execute(self, statement: Any) -> Any:
        self._sink.append(statement)
        return None

    async def __aenter__(self) -> _FakeConn:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


class _FakeEngine:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    def begin(self) -> _FakeConn:
        return _FakeConn(self.statements)

    connect = begin


def _deferred() -> Settings:
    return Settings(_env_file=None, kos_defer_vault_writes=True)


async def test_create_note_encola_y_devuelve_la_ruta_prevista() -> None:
    engine = _FakeEngine()
    path, deferred = await create_note_or_enqueue(
        engine,  # type: ignore[arg-type]
        _deferred(),
        source_name="vault-real",
        template_name="MaquinaHTB",
        folder="Security/HTB",
        title="Fawn",
    )
    assert deferred is True
    assert path == "Security/HTB/Fawn.md"
    assert len(engine.statements) == 1


async def test_update_y_create_folder_tambien_se_encolan() -> None:
    engine = _FakeEngine()
    path, deferred = await update_note_or_enqueue(
        engine,  # type: ignore[arg-type]
        _deferred(),
        source_name="vault-real",
        path="nota.md",
        content="nuevo",
    )
    assert (path, deferred) == ("nota.md", True)
    folder, deferred_folder = await create_folder_or_enqueue(
        engine,  # type: ignore[arg-type]
        _deferred(),
        source_name="vault-real",
        path="Nueva/Carpeta",
    )
    assert (folder, deferred_folder) == ("Nueva/Carpeta", True)
    assert len(engine.statements) == 2


async def test_sin_diferir_escribe_de_verdad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """El modo local de doc 09 no cambia: se escribe al instante."""
    vault = tmp_path / "vault"
    (vault / "_Templates").mkdir(parents=True)
    (vault / "_Templates" / "Base.md").write_text("# {{title}}", encoding="utf-8")

    async def fake_vault_path(engine: Any, source_name: str) -> Path:
        return vault

    monkeypatch.setattr("kos_core.notes.get_vault_path", fake_vault_path)
    path, deferred = await create_note_or_enqueue(
        object(),  # type: ignore[arg-type]
        Settings(_env_file=None),
        source_name="vault-real",
        template_name="Base",
        folder="Notas",
        title="Real",
    )
    assert deferred is False
    assert Path(path).is_file()
