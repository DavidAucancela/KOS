"""GET /metrics — métricas Prometheus de la API (doc 09 §6)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine
from kos_core.observability import (
    BUSINESS_REGISTRY,
    METRICS_REGISTRY,
    mark_business_metrics_unavailable,
    record_business_snapshot,
)
from kos_core.storage import postgres as postgres_storage

logger = logging.getLogger(__name__)

router = APIRouter()

# Un scrape lento no debe colgar a Prometheus ni retener una conexión: pasado
# este tiempo se sirven las métricas de proceso y `kos_business_metrics_up 0`.
_BUSINESS_SNAPSHOT_TIMEOUT_S = 5.0


@router.get("/metrics", include_in_schema=False)
async def metrics(engine: AsyncEngine = Depends(postgres_engine)) -> Response:
    # Nunca 500: si Postgres falla, el scrape sigue devolviendo las métricas de
    # proceso (HTTP, ingesta, tokens) y avisa con `kos_business_metrics_up 0`.
    try:
        snapshot = await asyncio.wait_for(
            postgres_storage.business_metrics_snapshot(engine),
            timeout=_BUSINESS_SNAPSHOT_TIMEOUT_S,
        )
    except Exception:
        logger.warning("metricas_de_negocio_no_disponibles", exc_info=True)
        mark_business_metrics_unavailable()
    else:
        record_business_snapshot(snapshot)
    body = generate_latest(METRICS_REGISTRY) + generate_latest(BUSINESS_REGISTRY)
    return Response(body, media_type=CONTENT_TYPE_LATEST)
