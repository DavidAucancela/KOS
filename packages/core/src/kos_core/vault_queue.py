"""Cola de escrituras al vault (doc 14 §5).

En el despliegue gestionado el vault vive en el volumen del servicio cron, y un
volumen de Railway se adjunta a un solo servicio: la API **no tiene el
filesystem del vault**. Sin esto, crear una nota desde el chat fallaría allí.

La cola guarda la *intención* (plantilla, carpeta, título…), no el resultado:
la API no puede ni siquiera leer la plantilla para renderizarla. El drain, que
sí tiene el vault delante, la materializa y empuja el resultado al repo — por
eso una nota creada desde el chat aparece en minutos, no al instante.

Vive en `core` y no en una app porque la escriben la API y las herramientas MCP,
y la consumen los workers.
"""

from __future__ import annotations

import uuid as uuid_lib
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.storage.postgres import pending_vault_writes_table

VaultOp = Literal["create_note", "update_note", "create_folder"]


async def enqueue(
    engine: AsyncEngine, *, op: VaultOp, source_name: str, payload: dict[str, Any]
) -> uuid_lib.UUID:
    """Registra una escritura pendiente y devuelve su id."""
    write_id = uuid_lib.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            pending_vault_writes_table.insert().values(
                write_id=write_id,
                op=op,
                source_name=source_name,
                payload=payload,
                requested_at=datetime.now(UTC),
                status="pending",
            )
        )
    return write_id


async def pending(engine: AsyncEngine, *, limit: int = 200) -> list[dict[str, Any]]:
    """Escrituras por aplicar, en orden de llegada."""
    async with engine.connect() as conn:
        result = await conn.execute(
            select(pending_vault_writes_table)
            .where(pending_vault_writes_table.c.status == "pending")
            .order_by(pending_vault_writes_table.c.requested_at)
            .limit(limit)
        )
        return [dict(row) for row in result.mappings().all()]


async def count_pending(engine: AsyncEngine) -> int:
    """Cuántas escrituras esperan al próximo ciclo (lo que muestra /v1/ops/status)."""
    async with engine.connect() as conn:
        result = await conn.execute(
            select(pending_vault_writes_table.c.write_id).where(
                pending_vault_writes_table.c.status == "pending"
            )
        )
        return len(result.all())


async def mark_applied(engine: AsyncEngine, write_id: uuid_lib.UUID, *, result_path: str) -> None:
    await _close(engine, write_id, status="applied", result_path=result_path, error=None)


async def mark_failed(engine: AsyncEngine, write_id: uuid_lib.UUID, *, error: str) -> None:
    """Una escritura fallida no se reintenta sola: queda registrada con su error.

    Reintentar a ciegas repetiría el fallo en cada ciclo (una plantilla que no
    existe no va a aparecer), y peor: una nota ya creada volvería a intentarse.
    """
    await _close(engine, write_id, status="failed", result_path=None, error=error)


async def _close(
    engine: AsyncEngine,
    write_id: uuid_lib.UUID,
    *,
    status: str,
    result_path: str | None,
    error: str | None,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            pending_vault_writes_table.update()
            .where(pending_vault_writes_table.c.write_id == write_id)
            .values(
                status=status,
                applied_at=datetime.now(UTC),
                result_path=result_path,
                error=error,
            )
        )
