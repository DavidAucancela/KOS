"""/v1/ops/status — salud operativa del despliegue gestionado (ADR-0009).

En Railway el worker no es un proceso vivo sino un cron job que arranca dos
veces al día, drena la cola y sale (doc 14 §4). Su fallo característico es
silencioso: si una ejecución no termina, Railway salta las siguientes y la
ingesta se detiene sin que nada falle. Este endpoint es lo que convierte eso en
algo visible — la web lo consulta y avisa cuando `ingesta.stale` es true.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.auth import RateLimiter, client_ip
from kos_api.deps import postgres_engine, settings_dep
from kos_api.ops import railway
from kos_core import vault_queue
from kos_core.config import Settings
from kos_core.storage import postgres as postgres_storage

router = APIRouter(prefix="/v1/ops", tags=["ops"])

_HOUR_SECONDS = 3600.0
# Cada disparo arranca un contenedor y consume minutos de Railway: se limita
# aparte del rate limit general (ADR-0010), que razona en peticiones/minuto.
_trigger_limiter = RateLimiter()


class CronRun(BaseModel):
    started_at: datetime
    finished_at: datetime | None
    status: str
    tasks_drained: int
    detail: str | None


class IngestStatus(BaseModel):
    last_run: CronRun | None
    hours_since_last_run: float | None
    stale_after_hours: int
    stale: bool
    """True cuando la ingesta programada lleva demasiado sin correr — o nunca
    corrió. Es el aviso que la web muestra."""


class OpsStatus(BaseModel):
    now: datetime
    mode: Literal["local", "managed"]
    ingesta: IngestStatus
    escrituras_pendientes: int
    """Notas y carpetas encoladas esperando al drain (doc 14 §5). En el modo
    local siempre 0: allí se escriben al instante."""


@router.get("/status", response_model=OpsStatus)
async def ops_status(
    engine: AsyncEngine = Depends(postgres_engine),
    settings: Settings = Depends(settings_dep),
) -> OpsStatus:
    now = datetime.now(UTC)
    row = await postgres_storage.last_cron_run(engine)
    last_run = CronRun(**row) if row else None

    hours: float | None = None
    if last_run is not None:
        reference = last_run.finished_at or last_run.started_at
        hours = round((now - reference).total_seconds() / 3600, 2)

    # Nunca haber corrido cuenta como parada: en el despliegue gestionado el
    # cron es la única vía de ingesta automática.
    stale = hours is None or hours > settings.kos_cron_stale_hours
    return OpsStatus(
        now=now,
        mode="managed" if settings.kos_serverless_mode else "local",
        escrituras_pendientes=await vault_queue.count_pending(engine),
        ingesta=IngestStatus(
            last_run=last_run,
            hours_since_last_run=hours,
            stale_after_hours=settings.kos_cron_stale_hours,
            stale=stale,
        ),
    )


class SyncNowAccepted(BaseModel):
    deployment_id: str
    detail: str


@router.post("/sync-now", response_model=SyncNowAccepted, status_code=202)
async def sync_now(
    request: Request,
    engine: AsyncEngine = Depends(postgres_engine),
    settings: Settings = Depends(settings_dep),
) -> SyncNowAccepted:
    """Ejecuta ahora el drain en vez de esperar al siguiente ciclo (doc 14 §5).

    La API no ingiere por sí misma: el vault está en el volumen del servicio
    cron y un volumen solo se adjunta a un servicio. Lo que hace es pedirle a
    Railway que ejecute ese servicio ya.
    """
    if not railway.is_configured(settings):
        raise HTTPException(
            status_code=501,
            detail=(
                "El disparo inmediato solo existe en el despliegue gestionado: "
                "faltan las credenciales de Railway."
            ),
        )

    running = await postgres_storage.last_cron_run(engine)
    if running is not None and running["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="Ya hay una ejecución del drain en curso; espera a que termine.",
        )

    if not _trigger_limiter.allow(
        client_ip(request), "sync-now", settings.kos_sync_now_per_hour, window=_HOUR_SECONDS
    ):
        raise HTTPException(
            status_code=429,
            detail=f"Límite de {settings.kos_sync_now_per_hour} disparos por hora superado.",
            headers={"Retry-After": "600"},
        )

    try:
        deployment_id = await railway.trigger_cron_run(settings)
    except railway.RailwayTriggerError as exc:
        raise HTTPException(status_code=502, detail=f"Railway rechazó el disparo: {exc}") from exc

    return SyncNowAccepted(
        deployment_id=deployment_id,
        detail="Drain disparado; la ingesta corre en el servicio cron.",
    )
