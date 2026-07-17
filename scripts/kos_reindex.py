"""`kos reindex` (doc 05 §5, doc 09 §backup): reconstruye los derivados desde MinIO + fuentes.

Encola `kos.sync_source` con `force=True` para una fuente (o todas), ignorando
los content_hash conocidos: reencola la ingesta completa de lo que discover()
devuelva y retira (tombstone) lo que ya no aparezca en la fuente.

Uso:
    uv run python scripts/kos_reindex.py                  # todas las fuentes habilitadas
    uv run python scripts/kos_reindex.py --source <name>  # una sola, por nombre
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from kos_api.services.source_service import enqueue_sync
from kos_core.config import get_settings
from kos_core.storage.postgres import create_engine, sources_table


async def _enabled_sources(source_name: str | None) -> list[dict[str, object]]:
    settings = get_settings()
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            query = select(sources_table).where(sources_table.c.enabled.is_(True))
            if source_name is not None:
                query = query.where(sources_table.c.name == source_name)
            rows = [dict(row) for row in (await conn.execute(query)).mappings().all()]
        if source_name is not None and not rows:
            raise SystemExit(f"Fuente no encontrada o deshabilitada: {source_name!r}")
        return rows
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=None, help="Nombre de una fuente; por defecto, todas")
    args = parser.parse_args()

    settings = get_settings()
    sources = asyncio.run(_enabled_sources(args.source))
    if not sources:
        print("No hay fuentes habilitadas.")
        return

    for source in sources:
        job_id = enqueue_sync(settings, source["source_uuid"], force=True)
        print(f"✓ reindex encolado — {source['name']!r} ({source['connector']}) → job {job_id}")


if __name__ == "__main__":
    main()
