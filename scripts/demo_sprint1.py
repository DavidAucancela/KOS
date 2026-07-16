"""Demo del Sprint 1 (doc 08): embebe un texto con bge-m3 y lo guarda en pgvector.

Requisitos: `make up`, `make pull-models` y `make migrate`.
Uso: `make demo`.
"""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from kos_core.config import get_settings
from kos_core.llm.ollama import OllamaEmbeddingClient
from kos_core.schemas import make_doc_id
from kos_core.storage.postgres import chunks_table, create_engine, documents_table

TEXT = "KOS es un motor de conocimiento independiente de fuentes; Obsidian es solo un conector."
QUERY = "¿Qué es KOS?"


async def main() -> None:
    settings = get_settings()

    embedder = OllamaEmbeddingClient(settings)
    try:
        doc_vector, query_vector = await embedder.embed([TEXT, QUERY])
    finally:
        await embedder.aclose()
    print(f"✓ Embedding con {settings.ollama_embedding_model}: {len(doc_vector)} dimensiones")

    doc_id = make_doc_id("demo", "sprint-1")
    engine = create_engine(settings)
    try:
        async with engine.begin() as conn:
            # La demo es re-ejecutable: borra el documento anterior (cascade a chunks).
            await conn.execute(documents_table.delete().where(documents_table.c.doc_id == doc_id))
            await conn.execute(
                documents_table.insert().values(
                    doc_id=doc_id,
                    connector="demo",
                    source_id="sprint-1",
                    title="Demo Sprint 1 — Hola, KOS",
                    fetched_at=datetime.now(UTC),
                )
            )
            await conn.execute(
                chunks_table.insert().values(
                    chunk_id=uuid.uuid4(),
                    doc_id=doc_id,
                    text=TEXT,
                    position=0,
                    start_offset=0,
                    end_offset=len(TEXT),
                    embedding=doc_vector,
                )
            )
        print("✓ Documento y chunk guardados en Postgres (pgvector)")

        async with engine.connect() as conn:
            distance = chunks_table.c.embedding.cosine_distance(query_vector)
            result = await conn.execute(
                select(chunks_table.c.text, distance.label("distance"))
                .where(chunks_table.c.embedding.is_not(None))
                .order_by(distance)
                .limit(1)
            )
            row = result.one()
        print(f"✓ Búsqueda vectorial para “{QUERY}” → “{row.text}” (distancia {row.distance:.4f})")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
