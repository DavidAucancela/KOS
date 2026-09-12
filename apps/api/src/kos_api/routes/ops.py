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

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine, settings_dep
from kos_core.config import Settings
from kos_core.storage import postgres as postgres_storage

router = APIRouter(prefix="/v1/ops", tags=["ops"])


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
        ingesta=IngestStatus(
            last_run=last_run,
            hours_since_last_run=hours,
            stale_after_hours=settings.kos_cron_stale_hours,
            stale=stale,
        ),
    )
