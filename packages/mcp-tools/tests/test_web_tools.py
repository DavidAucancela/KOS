"""Tests unitarios de `kos_mcp.tools.web` (Sprint 20): `httpx.AsyncClient`
fake, sin red real."""

from __future__ import annotations

from typing import Any

import pytest

from kos_mcp.tools import web as web_tools


class _FakeSearchResponse:
    status_code = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeSearchClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.requests: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    async def get(
        self, path: str, *, params: dict[str, Any], headers: dict[str, Any]
    ) -> _FakeSearchResponse:
        self.requests.append((path, params, headers))
        return _FakeSearchResponse(self._payload)


class _FakePageResponse:
    is_redirect = False

    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _FakePageClient:
    def __init__(self, text: str) -> None:
        self._text = text

    async def get(self, url: str, *, follow_redirects: bool) -> _FakePageResponse:
        return _FakePageResponse(self._text)


def _fake_addrinfo(ip: str) -> list[tuple[Any, Any, Any, str, tuple[str, int]]]:
    import socket as socket_module

    return [(socket_module.AF_INET, socket_module.SOCK_STREAM, 0, "", (ip, 443))]


async def test_search_core_lanza_sin_api_key() -> None:
    client = _FakeSearchClient({"web": {"results": []}})

    with pytest.raises(web_tools.MissingApiKeyError):
        await web_tools._search_core(client, "fastapi", 5, "")


async def test_search_core_mapea_resultados_con_key() -> None:
    client = _FakeSearchClient(
        {
            "web": {
                "results": [
                    {
                        "title": "FastAPI",
                        "url": "https://fastapi.tiangolo.com",
                        "description": "docs",
                    }
                ]
            }
        }
    )

    results = await web_tools._search_core(client, "fastapi", 5, "key123")

    assert results[0].title == "FastAPI"
    assert client.requests[0][2]["X-Subscription-Token"] == "key123"


async def test_search_core_lanza_rate_limited_en_429() -> None:
    response = _FakeSearchResponse({})
    response.status_code = 429

    class _RateLimitedClient(_FakeSearchClient):
        async def get(self, path: str, *, params: Any, headers: Any) -> _FakeSearchResponse:
            return response

    with pytest.raises(web_tools.RateLimitedError):
        await web_tools._search_core(_RateLimitedClient({}), "fastapi", 5, "key123")


async def test_open_core_extrae_texto_y_titulo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        web_tools.socket, "getaddrinfo", lambda *a, **kw: _fake_addrinfo("93.0.0.1")
    )
    html = "<html><head><title>Hola</title></head><body><p>Mundo</p></body></html>"
    client = _FakePageClient(html)

    result = await web_tools._open_core(client, "https://x.com")

    assert result.title == "Hola"
    assert "Mundo" in result.text
    assert "<p>" not in result.text


async def test_open_core_trunca_texto_largo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        web_tools.socket, "getaddrinfo", lambda *a, **kw: _fake_addrinfo("93.0.0.1")
    )
    html = "<p>" + ("a" * 10000) + "</p>"
    client = _FakePageClient(html)

    result = await web_tools._open_core(client, "https://x.com")

    assert len(result.text) == web_tools._OPEN_MAX_CHARS


async def test_open_core_bloquea_ip_privada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        web_tools.socket, "getaddrinfo", lambda *a, **kw: _fake_addrinfo("10.0.0.5")
    )
    client = _FakePageClient("<p>no debería llegar acá</p>")

    with pytest.raises(web_tools.BlockedUrlError, match="no público"):
        await web_tools._open_core(client, "https://internal.example")


async def test_open_core_bloquea_metadata_endpoint_de_nube(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        web_tools.socket, "getaddrinfo", lambda *a, **kw: _fake_addrinfo("169.254.169.254")
    )
    client = _FakePageClient("<p>secrets</p>")

    with pytest.raises(web_tools.BlockedUrlError):
        await web_tools._open_core(client, "http://169.254.169.254/latest/meta-data")


async def test_open_core_bloquea_esquema_no_http() -> None:
    client = _FakePageClient("no debería llegar acá")

    with pytest.raises(web_tools.BlockedUrlError, match="esquema"):
        await web_tools._open_core(client, "file:///etc/passwd")


async def test_guard_public_url_permite_ip_publica(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        web_tools.socket, "getaddrinfo", lambda *a, **kw: _fake_addrinfo("93.0.0.1")
    )

    await web_tools._guard_public_url("https://fastapi.tiangolo.com")  # no debe lanzar


async def test_guard_public_url_bloquea_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        web_tools.socket, "getaddrinfo", lambda *a, **kw: _fake_addrinfo("127.0.0.1")
    )

    with pytest.raises(web_tools.BlockedUrlError):
        await web_tools._guard_public_url("http://localhost:8000/admin")
