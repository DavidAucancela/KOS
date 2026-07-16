"""GET /health — estado de la infraestructura (entregable del Sprint 1, doc 08)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from kos_core.config import Settings
from kos_core.llm import ollama
from kos_core.storage import minio as minio_storage
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage import postgres as postgres_storage
from kos_core.storage import redis as redis_storage

router = APIRouter()

CHECK_TIMEOUT_SECONDS = 3.0

Checker = Callable[[Request], Awaitable[None]]


class ServiceStatus(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: float
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    services: dict[str, ServiceStatus]


async def _check_postgres(request: Request) -> None:
    await postgres_storage.ping(request.app.state.postgres_engine)


async def _check_neo4j(request: Request) -> None:
    await neo4j_storage.ping(request.app.state.neo4j_driver)


async def _check_redis(request: Request) -> None:
    await redis_storage.ping(request.app.state.redis_client)


async def _check_minio(request: Request) -> None:
    settings: Settings = request.app.state.settings
    await asyncio.to_thread(
        minio_storage.ping, request.app.state.minio_client, settings.minio_bucket
    )


async def _check_ollama(request: Request) -> None:
    settings: Settings = request.app.state.settings
    await ollama.ping(settings, timeout=CHECK_TIMEOUT_SECONDS)


# Los tests monkeypatchean este dict; su orden fija el orden en la respuesta.
CHECKS: dict[str, Checker] = {
    "postgres": _check_postgres,
    "neo4j": _check_neo4j,
    "redis": _check_redis,
    "minio": _check_minio,
    "ollama": _check_ollama,
}


async def _run_check(name: str, checker: Checker, request: Request) -> tuple[str, ServiceStatus]:
    started = time.perf_counter()
    try:
        await asyncio.wait_for(checker(request), timeout=CHECK_TIMEOUT_SECONDS)
    except Exception as exc:  # un servicio caído no tumba /health
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        detail = str(exc) or exc.__class__.__name__
        return name, ServiceStatus(status="error", latency_ms=latency_ms, detail=detail)
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    return name, ServiceStatus(status="ok", latency_ms=latency_ms)


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Verifica todos los servicios en paralelo; responde 200 siempre."""
    results = await asyncio.gather(
        *(_run_check(name, checker, request) for name, checker in CHECKS.items())
    )
    services = dict(results)
    all_ok = all(service.status == "ok" for service in services.values())
    return HealthResponse(status="ok" if all_ok else "degraded", services=services)
