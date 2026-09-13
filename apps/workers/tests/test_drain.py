"""Drain programado del despliegue gestionado (doc 14 §4, ADR-0009)."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from kos_core.config import Settings
from kos_workers import drain


class _FakeRedis:
    def __init__(self, pending: int, unacked: int) -> None:
        self._pending = pending
        self._unacked = unacked
        self.closed = False

    def llen(self, _key: str) -> int:
        return self._pending

    def hlen(self, _key: str) -> int:
        return self._unacked

    def close(self) -> None:
        self.closed = True


def _settings() -> Settings:
    return Settings(_env_file=None)


@pytest.mark.parametrize(
    ("pending", "unacked", "expected"),
    [
        (0, 0, True),
        (3, 0, False),
        # Una tarea entregada y aún sin confirmar no está en la lista: sin mirar
        # `unacked`, un drain con trabajo en curso parecería cola vacía.
        (0, 1, False),
    ],
)
def test_queue_is_empty(
    monkeypatch: pytest.MonkeyPatch, pending: int, unacked: int, expected: bool
) -> None:
    fake = _FakeRedis(pending, unacked)
    monkeypatch.setattr(drain.redis_storage, "create_sync_client", lambda settings: fake)
    assert drain.queue_is_empty(_settings()) is expected
    assert fake.closed, "el cliente tiene que cerrarse: el cron no deja conexiones abiertas"


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "vault"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "kos@test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "KOS"], check=True)
    (repo / "nota.md").write_text("# nota", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "inicial"], check=True)
    return repo


def test_pull_sin_repo_avisa_y_sigue(tmp_path: Path) -> None:
    """Un volumen sin repo no debe abortar la ingesta de lo que ya hay."""
    (tmp_path / "vault").mkdir()
    warning = drain.vault_pull(tmp_path / "vault")
    assert warning is not None
    assert "no es un repo git" in warning


def test_pull_fallido_no_aborta(tmp_path: Path) -> None:
    """Sin remoto configurado el pull falla: se avisa, no se rompe el ciclo."""
    repo = _git_repo(tmp_path)
    warning = drain.vault_pull(repo)
    assert warning is not None
    assert "git pull falló" in warning


def test_push_sin_cambios_no_hace_nada(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    assert drain.vault_push(repo, message="sin cambios") is None


def test_push_con_cambios_y_sin_remoto_avisa(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path)
    (repo / "nueva.md").write_text("creada por la ingesta", encoding="utf-8")
    warning = drain.vault_push(repo, message="kos: nota nueva")
    assert warning is not None
    assert "git push falló" in warning
    # El commit local sí se hizo: el push es lo único que faltó.
    assert (
        subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True
        ).stdout.strip()
        == ""
    )


async def test_consolidacion_de_memoria_toca_si_nunca_corrio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_last(engine: Any, *, job: str = "drain") -> dict[str, Any] | None:
        return None

    monkeypatch.setattr(drain.postgres_storage, "last_cron_run", fake_last)
    assert await drain._memory_consolidation_due(object(), _settings()) is True


@pytest.mark.parametrize(("hours", "expected"), [(30, True), (2, False)])
async def test_consolidacion_de_memoria_respeta_la_cadencia(
    monkeypatch: pytest.MonkeyPatch, hours: int, expected: bool
) -> None:
    """Se marca en cron_runs al encolarla; si no, correría en todos los ciclos."""

    async def fake_last(engine: Any, *, job: str = "drain") -> dict[str, Any] | None:
        return {
            "started_at": datetime.now(UTC) - timedelta(hours=hours),
            "finished_at": datetime.now(UTC) - timedelta(hours=hours),
        }

    monkeypatch.setattr(drain.postgres_storage, "last_cron_run", fake_last)
    assert await drain._memory_consolidation_due(object(), _settings()) is expected


class _QueueEngine:
    """Engine de mentira para el aplicador: devuelve la cola y recoge el cierre."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.applied: list[tuple[Any, str]] = []
        self.failed: list[tuple[Any, str]] = []


async def test_aplica_las_escrituras_pendientes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Lo que la API encoló se materializa aquí, que es quien tiene el vault."""
    vault = tmp_path / "vault"
    (vault / "_Templates").mkdir(parents=True)
    (vault / "_Templates" / "Base.md").write_text("# {{title}}", encoding="utf-8")

    engine = _QueueEngine(
        [
            {
                "write_id": "w1",
                "op": "create_note",
                "source_name": "vault-real",
                "payload": {"template_name": "Base", "folder": "Notas", "title": "Desde el chat"},
            }
        ]
    )

    async def fake_pending(_engine: Any, **_kw: Any) -> list[dict[str, Any]]:
        return engine.items

    async def fake_applied(_engine: Any, write_id: Any, *, result_path: str) -> None:
        engine.applied.append((write_id, result_path))

    async def fake_vault_path(_engine: Any, source_name: str) -> Path:
        return vault

    monkeypatch.setattr(drain.vault_queue, "pending", fake_pending)
    monkeypatch.setattr(drain.vault_queue, "mark_applied", fake_applied)
    monkeypatch.setattr(drain, "get_vault_path", fake_vault_path)

    applied, failed = await drain.apply_pending_writes(engine)
    assert (applied, failed) == (1, 0)
    assert (vault / "Notas" / "Desde el chat.md").is_file()
    assert engine.applied[0][0] == "w1"


async def test_una_escritura_rota_no_bloquea_las_demas(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Se marca con su error en vez de reintentarse en todos los ciclos."""
    vault = tmp_path / "vault"
    (vault / "_Templates").mkdir(parents=True)

    engine = _QueueEngine(
        [
            {
                "write_id": "rota",
                "op": "create_note",
                "source_name": "vault-real",
                "payload": {"template_name": "NoExiste", "folder": "N", "title": "X"},
            }
        ]
    )

    async def fake_pending(_engine: Any, **_kw: Any) -> list[dict[str, Any]]:
        return engine.items

    async def fake_failed(_engine: Any, write_id: Any, *, error: str) -> None:
        engine.failed.append((write_id, error))

    async def fake_vault_path(_engine: Any, source_name: str) -> Path:
        return vault

    monkeypatch.setattr(drain.vault_queue, "pending", fake_pending)
    monkeypatch.setattr(drain.vault_queue, "mark_failed", fake_failed)
    monkeypatch.setattr(drain, "get_vault_path", fake_vault_path)

    applied, failed = await drain.apply_pending_writes(engine)
    assert (applied, failed) == (0, 1)
    assert "Plantilla no encontrada" in engine.failed[0][1]
