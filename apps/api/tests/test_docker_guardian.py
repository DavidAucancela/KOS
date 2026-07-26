"""Tests del vigía de ahorro de recursos (doc 09 §8), sin Docker real."""

from __future__ import annotations

import time

import pytest

from kos_api.ops import docker_guardian
from kos_core.config import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(kos_activity_file=str(tmp_path / "activity"), kos_idle_stop_minutes=10)


def test_touch_activity_crea_el_archivo(settings: Settings) -> None:
    docker_guardian.touch_activity(settings)
    assert docker_guardian._last_activity(settings) == pytest.approx(time.time(), abs=2)


async def test_ensure_stack_up_no_reinicia_si_ya_esta_arriba(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(docker_guardian, "is_stack_up", _always_up)
    called: list[tuple[str, ...]] = []

    async def _fail_if_called(*args: str) -> tuple[int, str]:
        called.append(args)
        return 1, "no debería llamarse"

    monkeypatch.setattr(docker_guardian, "_run", _fail_if_called)

    assert await docker_guardian.ensure_stack_up(settings) is True
    assert called == []
    assert docker_guardian._last_activity(settings) is not None


async def test_ensure_stack_up_arranca_si_esta_caida(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, ...]] = []

    async def _fake_run(*args: str) -> tuple[int, str]:
        calls.append(args)
        return 0, ""

    monkeypatch.setattr(docker_guardian, "_run", _fake_run)
    monkeypatch.setattr(docker_guardian, "is_stack_up", _always_up_after_start(calls))

    assert await docker_guardian.ensure_stack_up(settings) is True
    assert any(call[1:3] == ("up", "-d") for call in calls)


async def test_ensure_stack_up_devuelve_false_si_falla_el_up(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(docker_guardian, "is_stack_up", _always_down)

    async def _fake_run(*args: str) -> tuple[int, str]:
        return 1, "docker no disponible"

    monkeypatch.setattr(docker_guardian, "_run", _fake_run)

    assert await docker_guardian.ensure_stack_up(settings) is False


async def test_stop_if_idle_sin_actividad_previa_no_hace_nada(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fail_if_called(*args: str) -> tuple[int, str]:
        raise AssertionError("no debería llamar a docker sin actividad registrada")

    monkeypatch.setattr(docker_guardian, "_run", _fail_if_called)

    assert await docker_guardian.stop_if_idle(settings) is False


async def test_stop_if_idle_bajo_el_umbral_no_apaga(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    docker_guardian.touch_activity(settings)
    monkeypatch.setattr(docker_guardian, "is_stack_up", _always_up)

    async def _fail_if_called(*args: str) -> tuple[int, str]:
        raise AssertionError("no debería apagar: actividad reciente")

    monkeypatch.setattr(docker_guardian, "_run", _fail_if_called)

    assert await docker_guardian.stop_if_idle(settings) is False


async def test_stop_if_idle_sobre_el_umbral_apaga(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = time.time() - (settings.kos_idle_stop_minutes + 1) * 60
    docker_guardian._activity_path(settings).write_text(str(old))
    monkeypatch.setattr(docker_guardian, "is_stack_up", _always_up)

    calls: list[tuple[str, ...]] = []

    async def _fake_run(*args: str) -> tuple[int, str]:
        calls.append(args)
        return 0, ""

    monkeypatch.setattr(docker_guardian, "_run", _fake_run)

    assert await docker_guardian.stop_if_idle(settings) is True
    assert calls[0][1] == "stop"


async def test_watch_deshabilitado_sale_sin_tocar_docker(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = settings.model_copy(update={"kos_guardian_enabled": False})

    async def _fail_if_called(*args: str) -> tuple[int, str]:
        raise AssertionError("no debería llamar a docker: guardian deshabilitado")

    monkeypatch.setattr(docker_guardian, "_run", _fail_if_called)

    await docker_guardian.watch(settings, interval_seconds=0.01)


async def _always_up(settings: Settings) -> bool:
    return True


async def _always_down(settings: Settings) -> bool:
    return False


def _always_up_after_start(calls: list[tuple[str, ...]]):
    async def _check(settings: Settings) -> bool:
        return any(call[1:3] == ("up", "-d") for call in calls)

    return _check
