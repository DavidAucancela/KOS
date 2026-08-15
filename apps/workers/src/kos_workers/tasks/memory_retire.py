"""Task de retiro de evidencia de memoria al tumbar un documento (Sprint 14,
doc 04 §5, doc 06 §3 `document.deleted`): contraparte de `kos.graph_retire_document`
para Postgres/memoria, encadenada desde `kos.sync_source` igual que esa — mismo
patrón de encadenado directo, no una suscripción al evento.
"""

from __future__ import annotations

import asyncio
from typing import Any

from kos_core.config import get_settings
from kos_core.storage import postgres as postgres_storage
from kos_core.storage.postgres import create_engine
from kos_workers.celery_app import app


async def _async_memory_retire_document(doc_id: str) -> dict[str, int]:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        return await postgres_storage.retire_memory_sources(engine, doc_id)
    finally:
        await engine.dispose()


@app.task(name="kos.memory_retire_document")
def memory_retire_document(doc_id: str) -> dict[str, Any]:
    """Retira `doc_id` de `sources[]` de las memorias que lo mencionan, recalcula
    `confidence` (doc 04 §5) y archiva las que quedan sin ninguna fuente."""
    return asyncio.run(_async_memory_retire_document(doc_id))
