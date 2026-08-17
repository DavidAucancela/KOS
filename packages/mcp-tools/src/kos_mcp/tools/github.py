"""Herramientas de lectura contra la API pública de GitHub: `github.search_repos`,
`github.search_commits` (doc 06 §4, Sprint 20). Sin `GITHUB_TOKEN` funcionan igual
con la cuota liviana de un cliente anónimo (60 req/hora); con token, la cuota
sube (5000 req/hora) — nunca requerido, solo mejora el límite.

Mismo patrón `_xxx_core(client, ...)` testeable con un `httpx.AsyncClient` fake
que ya usan `graph.py`/`vector.py` con sus storages.

Auditoría de cierre v0.5 (2026-08-16): `get_with_retry` (`_http.py`) reintenta
fallos de transporte; `RateLimitedError` distingue "sin cuota" (403/429) de un
error genérico, para que quien lea la traza sepa que no es un bug — es el
límite público de GitHub."""

from __future__ import annotations

import httpx
from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel

from kos_mcp.tools._http import get_with_retry

_BASE_URL = "https://api.github.com"
_TIMEOUT = 15.0


class RateLimitedError(Exception):
    """GitHub devolvió 403/429 — cuota de la API pública agotada."""


class GitHubRepoResult(BaseModel):
    full_name: str
    url: str
    description: str | None
    stars: int


class GitHubCommitResult(BaseModel):
    sha: str
    url: str
    message: str
    repo: str


def _headers(token: str) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _raise_for_status_or_rate_limit(response: httpx.Response, *, token: str) -> None:
    if response.status_code in (403, 429):
        hint = (
            "configurar GITHUB_TOKEN sube la cuota de 60 a 5000 req/hora"
            if not token
            else "cuota agotada pese a GITHUB_TOKEN configurado — esperar a que se renueve"
        )
        raise RateLimitedError(f"GitHub rate limit (status={response.status_code}): {hint}")
    response.raise_for_status()


async def _search_repos_core(
    client: httpx.AsyncClient, query: str, limit: int, token: str
) -> list[GitHubRepoResult]:
    response = await get_with_retry(
        client,
        "/search/repositories",
        params={"q": query, "per_page": limit},
        headers=_headers(token),
    )
    _raise_for_status_or_rate_limit(response, token=token)
    items = response.json().get("items", [])
    return [
        GitHubRepoResult(
            full_name=item["full_name"],
            url=item["html_url"],
            description=item.get("description"),
            stars=item.get("stargazers_count", 0),
        )
        for item in items
    ]


async def _search_commits_core(
    client: httpx.AsyncClient, query: str, limit: int, token: str
) -> list[GitHubCommitResult]:
    response = await get_with_retry(
        client,
        "/search/commits",
        params={"q": query, "per_page": limit},
        headers=_headers(token),
    )
    _raise_for_status_or_rate_limit(response, token=token)
    items = response.json().get("items", [])
    return [
        GitHubCommitResult(
            sha=item["sha"],
            url=item["html_url"],
            message=item["commit"]["message"].splitlines()[0],
            repo=item["repository"]["full_name"],
        )
        for item in items
    ]


def register(server: MCPServer) -> None:
    @server.tool(name="github.search_repos")
    async def github_search_repos(
        ctx: Context, query: str, limit: int = 5
    ) -> list[GitHubRepoResult]:
        """Repositorios públicos que matchean `query` (doc 06 §4, Fase 4)."""
        app_ctx = ctx.request_context.lifespan_context
        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=_TIMEOUT) as client:
            return await _search_repos_core(client, query, limit, app_ctx.settings.github_token)

    @server.tool(name="github.search_commits")
    async def github_search_commits(
        ctx: Context, query: str, limit: int = 5
    ) -> list[GitHubCommitResult]:
        """Commits públicos que matchean `query` (doc 06 §4, Fase 4)."""
        app_ctx = ctx.request_context.lifespan_context
        async with httpx.AsyncClient(base_url=_BASE_URL, timeout=_TIMEOUT) as client:
            return await _search_commits_core(client, query, limit, app_ctx.settings.github_token)
