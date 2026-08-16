"""Herramientas de lectura contra la API pública de GitHub: `github.search_repos`,
`github.search_commits` (doc 06 §4, Sprint 20). Sin `GITHUB_TOKEN` funcionan igual
con la cuota liviana de un cliente anónimo (60 req/hora); con token, la cuota
sube (5000 req/hora) — nunca requerido, solo mejora el límite.

Mismo patrón `_xxx_core(client, ...)` testeable con un `httpx.AsyncClient` fake
que ya usan `graph.py`/`vector.py` con sus storages."""

from __future__ import annotations

import httpx
from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel

_BASE_URL = "https://api.github.com"
_TIMEOUT = 15.0


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


async def _search_repos_core(
    client: httpx.AsyncClient, query: str, limit: int, token: str
) -> list[GitHubRepoResult]:
    response = await client.get(
        "/search/repositories",
        params={"q": query, "per_page": limit},
        headers=_headers(token),
    )
    response.raise_for_status()
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
    response = await client.get(
        "/search/commits",
        params={"q": query, "per_page": limit},
        headers=_headers(token),
    )
    response.raise_for_status()
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
