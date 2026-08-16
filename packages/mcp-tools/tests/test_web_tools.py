"""Tests unitarios de `kos_mcp.tools.web` (Sprint 20): `httpx.AsyncClient`
fake, sin red real."""

from __future__ import annotations

from typing import Any

import pytest

from kos_mcp.tools import web as web_tools


class _FakeSearchResponse:
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
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class _FakePageClient:
    def __init__(self, text: str) -> None:
        self._text = text

    async def get(self, url: str, *, follow_redirects: bool) -> _FakePageResponse:
        return _FakePageResponse(self._text)


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


async def test_open_core_extrae_texto_y_titulo() -> None:
    html = "<html><head><title>Hola</title></head><body><p>Mundo</p></body></html>"
    client = _FakePageClient(html)

    result = await web_tools._open_core(client, "https://x.com")

    assert result.title == "Hola"
    assert "Mundo" in result.text
    assert "<p>" not in result.text


async def test_open_core_trunca_texto_largo() -> None:
    html = "<p>" + ("a" * 10000) + "</p>"
    client = _FakePageClient(html)

    result = await web_tools._open_core(client, "https://x.com")

    assert len(result.text) == web_tools._OPEN_MAX_CHARS
