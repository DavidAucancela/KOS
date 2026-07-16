"""Task de embeddings por lotes (Sprint 3, doc 05 §3).

La etapa cara corre fuera de la ingesta: `kos.ingest_document` encola
`kos.embed_document`, que embebe con bge-m3 SOLO los chunks pendientes
(`embedding IS NULL`) y actualiza pgvector. Reejecutarla es inocuo.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.storage.postgres import chunks_table, create_engine
from kos_workers.celery_app import app
from kos_workers.tasks.enrich import enrich_document

BATCH_SIZE = 16

# Igual que EmbedBatch de la etapa s4, pero asíncrono (cliente Ollama real).
AsyncEmbedBatch = Callable[[Sequence[str]], Awaitable[list[list[float]]]]


async def _embed_in_batches(
    texts: Sequence[str], embed_batch: AsyncEmbedBatch, batch_size: int = BATCH_SIZE
) -> list[list[float]]:
    """Embebe en lotes preservando el orden global de los textos."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(await embed_batch(list(texts[start : start + batch_size])))
    return vectors


async def _embed_pending(
    doc_id: uuid.UUID, embed_batch: AsyncEmbedBatch, engine: AsyncEngine
) -> int:
    """Embebe y actualiza los chunks sin embedding del documento; devuelve cuántos."""
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                select(chunks_table.c.chunk_id, chunks_table.c.text)
                .where(
                    chunks_table.c.doc_id == doc_id,
                    chunks_table.c.embedding.is_(None),
                )
                .order_by(chunks_table.c.position)
            )
        ).all()
    if not rows:
        return 0

    vectors = await _embed_in_batches([row.text for row in rows], embed_batch)
    async with engine.begin() as conn:
        for row, vector in zip(rows, vectors, strict=True):
            await conn.execute(
                update(chunks_table)
                .where(chunks_table.c.chunk_id == row.chunk_id)
                .values(embedding=vector)
            )
    return len(rows)


async def _embed_document(doc_id: uuid.UUID) -> int:
    settings = get_settings()
    client = OllamaEmbeddingClient(settings)
    engine = create_engine(settings)
    try:
        return await _embed_pending(doc_id, client.embed, engine)
    finally:
        await client.aclose()
        await engine.dispose()


@app.task(name="kos.embed_document")
def embed_document(doc_id: str) -> dict[str, Any]:
    """Embebe con bge-m3 los chunks pendientes del documento (idempotente).

    Encadena el enriquecido (resumen + keywords), etapa cara aparte (doc 05 §3).
    """
    embedded = asyncio.run(_embed_document(uuid.UUID(doc_id)))
    enrich_document.delay(doc_id)
    return {"doc_id": doc_id, "embedded": embedded}
