"""Aristas `RELATED_TO` por co-ocurrencia de entidades (doc 12 §10.5).

Encadenada tras `kos.graph_sync` (mismo patrón de import diferido que
`kos.recommend_from_graph_update` / `kos.discover_cross_document_relations`).
Determinístico: una consulta agregada sobre `chunks.entity_node_ids` — sin LLM,
que en el hardware local no rinde para extracción de relaciones (doc 12 §10.2).

La pasada incremental acota el cálculo a los pares que tocan algún nodo del
documento recién sincronizado; el backfill (`scripts/backfill_graph_extraction.py`)
corre la pasada completa llamando `_async_discover_cooccurrence_relations()` sin
`touching_node_ids`.
"""

from __future__ import annotations

import asyncio
from typing import Any

from kos_core.config import get_settings
from kos_core.storage import neo4j as neo4j_storage
from kos_core.storage.postgres import create_engine
from kos_workers.celery_app import app
from kos_workers.tasks.graph_sync import sync_cooccurrence_relations


async def _async_discover_cooccurrence_relations(
    touching_node_ids: list[str] | None,
) -> dict[str, Any]:
    settings = get_settings()
    engine = create_engine(settings)
    driver = neo4j_storage.create_driver(settings)
    try:
        written = await sync_cooccurrence_relations(
            driver, engine, touching_node_ids=touching_node_ids
        )
        return {"relations_written": written, "incremental": touching_node_ids is not None}
    finally:
        await driver.close()
        await engine.dispose()


@app.task(name="kos.discover_cooccurrence_relations")
def discover_cooccurrence_relations(node_ids: list[str]) -> dict[str, Any]:
    return asyncio.run(_async_discover_cooccurrence_relations(node_ids or None))
