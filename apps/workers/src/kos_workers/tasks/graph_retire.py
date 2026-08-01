"""Task de retiro de evidencia del grafo al tumbar un documento (Sprint 11,
doc 05 §5, doc 06 §3 `document.deleted`): contraparte de `kos.graph_sync`,
encadenada directamente desde `kos.sync_source` cuando `_retire_missing`
encuentra documentos ausentes en la fuente — mismo patrón que
`embed_document.delay`/`graph_sync.delay`, no una suscripción al evento.
"""

from __future__ import annotations

import asyncio
from typing import Any

from kos_core.config import get_settings
from kos_core.storage import neo4j as neo4j_storage
from kos_workers.celery_app import app


async def _async_graph_retire_document(doc_id: str) -> dict[str, int]:
    settings = get_settings()
    driver = neo4j_storage.create_driver(settings)
    try:
        return await neo4j_storage.retire_document(driver, doc_id)
    finally:
        await driver.close()


@app.task(name="kos.graph_retire_document")
def graph_retire_document(doc_id: str) -> dict[str, Any]:
    """Retira `doc_id` de `sources[]` en Neo4j y borra lo que queda huérfano."""
    return asyncio.run(_async_graph_retire_document(doc_id))
