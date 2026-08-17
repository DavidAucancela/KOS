"""Herramientas de búsqueda/lectura web: `web.search` (Brave Search API),
`web.open` (fetch + extracción de texto plano) — doc 06 §4, Sprint 20.

A diferencia de `github.py`, `BRAVE_SEARCH_API_KEY` es requerida: sin ella no
hay forma de cumplir la tool, así que se lanza `MissingApiKeyError` con un
mensaje claro en vez de devolver una lista vacía (que un LLM podría leer como
"no hay resultados" en lugar de "falta configuración") — el Planner/executor
ya sabe degradar un paso de evidencia que lanza (`executor.py`, Sprint 18).

`web.open` (auditoría de cierre v0.5, 2026-08-16): `_guard_public_url()`
bloquea SSRF — `url` la elige el Planner (LLM), que a su vez puede verse
influenciado por contenido externo que trajo `web.search`, así que no es
input confiable. Resuelve el hostname y rechaza si cualquier IP resuelta cae
en un rango privado/loopback/link-local/reservado (incluye el endpoint de
metadata de nube, `169.254.169.254`) — mismo criterio que cualquier SSRF
guard estándar, sin permitir bypasses por redirección (se revalida en cada
salto, `follow_redirects=False` + loop manual)."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlparse

import httpx
from mcp.server.mcpserver import Context, MCPServer
from pydantic import BaseModel

from kos_mcp.tools._http import get_with_retry

_BRAVE_BASE_URL = "https://api.search.brave.com"
_TIMEOUT = 15.0
_OPEN_MAX_CHARS = 5000
_MAX_REDIRECTS = 5
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


class MissingApiKeyError(Exception):
    """`BRAVE_SEARCH_API_KEY` no está configurada (`.env`, doc 06 §4)."""


class BlockedUrlError(Exception):
    """`url` resuelve a una dirección no pública (SSRF guard, `web.open`)."""


class RateLimitedError(Exception):
    """Brave Search devolvió 429 — cuota de la API agotada (auditoría de
    cierre v0.5, 2026-08-16)."""


async def _guard_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise BlockedUrlError(f"esquema no permitido: {parsed.scheme!r} (solo http/https)")
    if not parsed.hostname:
        raise BlockedUrlError(f"URL sin host: {url!r}")

    try:
        addrinfo = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, None)
    except socket.gaierror as exc:
        raise BlockedUrlError(f"no se pudo resolver {parsed.hostname!r}: {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in addrinfo:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise BlockedUrlError(
                f"{parsed.hostname!r} resuelve a {ip} (no público) — bloqueado (SSRF guard)"
            )


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
    response = await get_with_retry(
        client,
        "/res/v1/web/search",
        params={"q": query, "count": limit},
        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
    )
    if response.status_code == 429:
        raise RateLimitedError("Brave Search rate limit alcanzado (status=429)")
    response.raise_for_status()
    results = response.json().get("web", {}).get("results", [])
    return [
        WebSearchResult(title=item["title"], url=item["url"], snippet=item.get("description", ""))
        for item in results[:limit]
    ]


async def _open_core(client: httpx.AsyncClient, url: str) -> WebOpenResult:
    """Sigue redirecciones a mano (`follow_redirects=False` + loop), revalidando
    la URL de cada salto — seguir con `follow_redirects=True` dejaría pasar un
    salto a una IP interna después de que la URL original pasara el guard."""
    current_url = url
    for _hop in range(_MAX_REDIRECTS + 1):
        await _guard_public_url(current_url)
        response = await get_with_retry(client, current_url, follow_redirects=False)
        if response.is_redirect:
            current_url = str(response.next_request.url) if response.next_request else current_url
            continue
        response.raise_for_status()
        text = _strip_html(response.text)[:_OPEN_MAX_CHARS]
        return WebOpenResult(url=current_url, title=_extract_title(response.text), text=text)
    raise BlockedUrlError(f"demasiadas redirecciones (> {_MAX_REDIRECTS}) desde {url!r}")


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
