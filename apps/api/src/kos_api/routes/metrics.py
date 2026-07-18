"""GET /metrics — métricas Prometheus de la API (doc 09 §6)."""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from kos_core.observability import METRICS_REGISTRY

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(METRICS_REGISTRY), media_type=CONTENT_TYPE_LATEST)
