"""Backfill del grafo con el pipeline nuevo (doc 12 §6): re-extrae entidades y
relaciones (resolución indexada — PR 1, por chunk — PR 2, cross-documento —
PR 3) para los documentos ya ingeridos, sin re-fetch/re-embed/re-resumen —
`kos reindex` (doc 05 §5, `scripts/kos_reindex.py`) rehace todo el pipeline
desde la fuente, trabajo que acá no hace falta: los chunks y sus embeddings
en Postgres ya son correctos, solo cambió cómo se extraen entidades/relaciones
a partir de ellos.

Llama directo `_async_graph_sync`/`_async_discover_cross_document_relations`,
sin pasar por Celery (mismo criterio que `scripts/backfill_node_embeddings.py`,
PR 1): un `.delay()` sin worker corriendo solo encola, no ejecuta.

Idempotente por diseño (MERGE en Neo4j, doc 02 §4, ADR-0003) — correr de
nuevo (o interrumpir a mitad de camino y retomar con `--limit`) no duplica
nada, solo reescribe lo mismo o suma evidencia nueva.

Costo esperado: cada chunk es como mínimo una llamada LLM (entidades), más
relaciones intra-documento y cross-documento cuando aplica — con el volumen
real del vault (714 documentos, 2.539 chunks al momento de escribir esto)
esto corre varias horas contra Ollama local. Usar `--limit N` para correr en
tandas en vez de todo de una sola vez.

Uso:
    uv run python scripts/backfill_graph_extraction.py              # todos
    uv run python scripts/backfill_graph_extraction.py --limit 25   # los primeros 25
"""

from __future__ import annotations

import argparse
import asyncio
import uuid

from sqlalchemy import select

from kos_core.config import get_settings
from kos_core.storage.postgres import create_engine, documents_table
from kos_workers.tasks.cross_doc_relations import _async_discover_cross_document_relations
from kos_workers.tasks.graph_sync import _async_graph_sync


async def _active_doc_ids(limit: int | None) -> list[uuid.UUID]:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        query = (
            select(documents_table.c.doc_id)
            .where(documents_table.c.deleted_at.is_(None))
            .order_by(documents_table.c.doc_id)
        )
        if limit is not None:
            query = query.limit(limit)
        async with engine.connect() as conn:
            return list((await conn.execute(query)).scalars().all())
    finally:
        await engine.dispose()


async def _backfill(limit: int | None) -> None:
    doc_ids = await _active_doc_ids(limit)
    print(f"Backfill de {len(doc_ids)} documento(s)...")
    for i, doc_id in enumerate(doc_ids, 1):
        result = await _async_graph_sync(doc_id)
        cross_doc = {"chunks_checked": 0, "relations_written": 0}
        if result.get("synced") and result.get("chunk_ids"):
            cross_doc = await _async_discover_cross_document_relations(
                doc_id=result["doc_id"], chunk_ids=result["chunk_ids"]
            )
        print(
            f"[{i}/{len(doc_ids)}] {doc_id}: "
            f"{result.get('entities', 0)} entidades, {result.get('relations', 0)} relaciones, "
            f"cross-doc: {cross_doc['chunks_checked']} revisados/"
            f"{cross_doc['relations_written']} nuevas"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=None, help="Procesa solo los primeros N documentos"
    )
    args = parser.parse_args()
    asyncio.run(_backfill(args.limit))


if __name__ == "__main__":
    main()
