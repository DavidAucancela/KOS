"""Tests unitarios de `kos_mcp.tools._http.get_with_retry` (auditoría de
cierre v0.5, 2026-08-16): reintenta fallos de transporte, no respuestas HTTP."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from kos_mcp.tools._http import get_with_retry


class _FlakyClient:
    """Falla las primeras `fail_times` llamadas con un error de transporte,
    después responde 200."""

    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise httpx.ConnectError("conexión rechazada")
        return httpx.Response(200)


async def test_reintenta_hasta_tener_exito(monkeypatch: pytest.MonkeyPatch) -> None:
    import kos_mcp.tools._http as http_module

    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(http_module.asyncio, "sleep", no_sleep)

    client = _FlakyClient(fail_times=2)
    response = await get_with_retry(client, "https://x.com")

    assert response.status_code == 200
    assert client.calls == 3


async def test_propaga_el_error_tras_agotar_reintentos(monkeypatch: pytest.MonkeyPatch) -> None:
    import kos_mcp.tools._http as http_module

    async def no_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(http_module.asyncio, "sleep", no_sleep)

    client = _FlakyClient(fail_times=99)

    with pytest.raises(httpx.ConnectError):
        await get_with_retry(client, "https://x.com")

    assert client.calls == http_module._MAX_RETRIES + 1


async def test_no_reintenta_una_respuesta_http_valida() -> None:
    client = _FlakyClient(fail_times=0)

    await get_with_retry(client, "https://x.com")

    assert client.calls == 1
