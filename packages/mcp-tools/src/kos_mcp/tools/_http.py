"""Retry con backoff corto para fallos de transporte (timeout, conexión) en
herramientas MCP que llaman APIs externas (`github.py`, `web.py`) — auditoría
de cierre v0.5, 2026-08-16.

Solo reintenta `httpx.TransportError` (timeout/conexión) — nunca una
respuesta HTTP ya recibida (4xx/5xx): esas son respuestas reales del
servidor, no fallos de red, y reintentar un rate limit sin esperar la
ventana completa no ayuda (cada tool detecta 403/429 por su cuenta, ver
`github.RateLimitedError`/`web.RateLimitedError`)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

_MAX_RETRIES = 2
_BACKOFF_SECONDS = 0.5


async def get_with_retry(client: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response:
    last_exc: httpx.TransportError | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return await client.get(url, **kwargs)
        except httpx.TransportError as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_BACKOFF_SECONDS * (attempt + 1))
    assert last_exc is not None  # el loop siempre retorna o deja last_exc seteado
    raise last_exc
