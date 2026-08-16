"""Herramientas de búsqueda/lectura web: `web.search` (Brave Search API),
`web.open` (fetch + extracción de texto plano) — doc 06 §4, Sprint 20.

A diferencia de `github.py`, `BRAVE_SEARCH_API_KEY` es requerida: sin ella no
hay forma de cumplir la tool, así que se lanza `MissingApiKeyError` con un
mensaje claro en vez de devolver una lista vacía (que un LLM podría leer como
"no hay resultados" en lugar de "falta configuración") — el Planner/executor
ya sabe degradar un paso de evidencia que lanza (`executor.py`, Sprint 18)."""

from __future__ import annotations

import re

import httpx
from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel

_BRAVE_BASE_URL = "https://api.search.brave.com"
_TIMEOUT = 15.0
_OPEN_MAX_CHARS = 5000
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


class MissingApiKeyError(Exception):
    """`BRAVE_SEARCH_API_KEY` no está configurada (`.env`, doc 06 §4)."""


class WebSearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class WebOpenResult(BaseModel):
    url: str
    title: str | None
    text: str


def _strip_html(html: str) -> str:
    without_tags = _TAG_RE.sub(" ", html)
    return _WHITESPACE_RE.sub(" ", without_tags).strip()


def _extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return _WHITESPACE_RE.sub(" ", match.group(1)).strip() if match else None


async def _search_core(
    client: httpx.AsyncClient, query: str, limit: int, api_key: str
) -> list[WebSearchResult]:
    if not api_key:
        raise MissingApiKeyError("BRAVE_SEARCH_API_KEY no está configurada (.env, doc 06 §4)")
    response = await client.get(
        "/res/v1/web/search",
        params={"q": query, "count": limit},
        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
    )
    response.raise_for_status()
    results = response.json().get("web", {}).get("results", [])
    return [
        WebSearchResult(title=item["title"], url=item["url"], snippet=item.get("description", ""))
        for item in results[:limit]
    ]


async def _open_core(client: httpx.AsyncClient, url: str) -> WebOpenResult:
    response = await client.get(url, follow_redirects=True)
    response.raise_for_status()
    text = _strip_html(response.text)[:_OPEN_MAX_CHARS]
    return WebOpenResult(url=url, title=_extract_title(response.text), text=text)


def register(server: MCPServer) -> None:
    @server.tool(name="web.search")
    async def web_search(ctx: Context, query: str, limit: int = 5) -> list[WebSearchResult]:
        """Búsqueda web vía Brave Search API (doc 06 §4, Fase 4). Lanza
        `MissingApiKeyError` si `BRAVE_SEARCH_API_KEY` no está configurada."""
        app_ctx = ctx.request_context.lifespan_context
        async with httpx.AsyncClient(base_url=_BRAVE_BASE_URL, timeout=_TIMEOUT) as client:
            return await _search_core(client, query, limit, app_ctx.settings.brave_search_api_key)

    @server.tool(name="web.open")
    async def web_open(ctx: Context, url: str) -> WebOpenResult:
        """Trae `url` y devuelve su texto plano (sin tags), truncado a
        `_OPEN_MAX_CHARS` (doc 06 §4, Fase 4)."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            return await _open_core(client, url)
