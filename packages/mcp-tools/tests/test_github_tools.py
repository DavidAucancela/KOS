"""Tests unitarios de `kos_mcp.tools.github` (Sprint 20): `httpx.AsyncClient`
fake, sin red real."""

from __future__ import annotations

from typing import Any

import pytest

from kos_mcp.tools import github as github_tools


class _FakeResponse:
    status_code = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.requests: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    async def get(
        self, path: str, *, params: dict[str, Any], headers: dict[str, Any]
    ) -> _FakeResponse:
        self.requests.append((path, params, headers))
        return _FakeResponse(self._payload)


async def test_search_repos_core_mapea_items() -> None:
    client = _FakeClient(
        {
            "items": [
                {
                    "full_name": "tiangolo/fastapi",
                    "html_url": "https://github.com/tiangolo/fastapi",
                    "description": "FastAPI framework",
                    "stargazers_count": 70000,
                }
            ]
        }
    )

    results = await github_tools._search_repos_core(client, "fastapi", 5, "")

    assert results[0].full_name == "tiangolo/fastapi"
    assert client.requests[0][2] == {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def test_search_repos_core_agrega_token_si_esta_presente() -> None:
    client = _FakeClient({"items": []})

    await github_tools._search_repos_core(client, "fastapi", 5, "tok123")

    assert client.requests[0][2]["Authorization"] == "Bearer tok123"


async def test_search_commits_core_toma_el_primer_renglon() -> None:
    client = _FakeClient(
        {
            "items": [
                {
                    "sha": "abc123",
                    "html_url": "https://github.com/x/y/commit/abc123",
                    "commit": {"message": "fix: algo\n\ndetalle"},
                    "repository": {"full_name": "x/y"},
                }
            ]
        }
    )

    results = await github_tools._search_commits_core(client, "fix", 5, "")

    assert results[0].message == "fix: algo"
    assert results[0].repo == "x/y"


async def test_search_repos_core_lanza_rate_limited_en_403() -> None:
    client_response = _FakeResponse({})
    client_response.status_code = 403

    class _RateLimitedClient(_FakeClient):
        async def get(self, path: str, *, params: Any, headers: Any) -> _FakeResponse:
            return client_response

    with pytest.raises(github_tools.RateLimitedError, match="GITHUB_TOKEN"):
        await github_tools._search_repos_core(_RateLimitedClient({}), "fastapi", 5, "")


async def test_search_repos_core_403_con_token_no_menciona_configurar_token() -> None:
    client_response = _FakeResponse({})
    client_response.status_code = 403

    class _RateLimitedClient(_FakeClient):
        async def get(self, path: str, *, params: Any, headers: Any) -> _FakeResponse:
            return client_response

    with pytest.raises(github_tools.RateLimitedError, match="esperar a que se renueve"):
        await github_tools._search_repos_core(_RateLimitedClient({}), "fastapi", 5, "tok123")
