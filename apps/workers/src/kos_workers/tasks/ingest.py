"""Tasks de ingesta (Sprint 2, doc 05): fuente → conector → parser → almacenes.

`kos.sync_source` descubre los documentos de una fuente registrada y encola
`kos.ingest_document` por cada uno cuyo `content_hash` cambió (idempotencia,
doc 05 §5). La ingesta guarda el blob original en MinIO (inmutable), persiste
el `ParsedDocument` en Postgres y emite los eventos del bus (doc 06 §3).
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from sqlalchemy import select

from kos_connectors.base import Connector, SourceRef
from kos_connectors.registry import get_connector
from kos_core.config import Settings, get_settings
from kos_core.schemas import make_doc_id
from kos_core.schemas.events import DocumentIngested, DocumentParsed
from kos_core.storage import minio as minio_storage
from kos_core.storage import redis as redis_storage
from kos_core.storage.postgres import (
    create_engine,
    documents_table,
    sources_table,
    upsert_parsed_document,
)
from kos_workers.celery_app import app
from kos_workers.pipeline import PIPELINE_VERSION, run_pipeline
from kos_workers.tasks.embed import embed_document


async def _load_source(source_uuid: uuid.UUID, settings: Settings) -> dict[str, Any] | None:
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            row = (
                (
                    await conn.execute(
                        select(sources_table).where(sources_table.c.source_uuid == source_uuid)
                    )
                )
                .mappings()
                .first()
            )
            return dict(row) if row else None
    finally:
        await engine.dispose()


async def _known_hashes(connector_name: str, settings: Settings) -> dict[str, str]:
    """content_hash registrado por source_id, para saltar documentos sin cambios."""
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                select(documents_table.c.source_id, documents_table.c.content_hash).where(
                    documents_table.c.connector == connector_name
                )
            )
            return {row.source_id: row.content_hash for row in result if row.content_hash}
    finally:
        await engine.dispose()


def _build_connector(source: dict[str, Any]) -> Connector:
    config: dict[str, Any] = source.get("config") or {}
    return get_connector(str(source["connector"]), **config)


@app.task(name="kos.sync_source")
def sync_source(source_uuid: str) -> dict[str, int]:
    """Descubre la fuente y encola la ingesta de lo nuevo/cambiado."""
    settings = get_settings()
    source = asyncio.run(_load_source(uuid.UUID(source_uuid), settings))
    if source is None or not source["enabled"]:
        return {"discovered": 0, "queued": 0, "skipped": 0}

    connector = _build_connector(source)
    known = asyncio.run(_known_hashes(connector.name, settings))

    discovered = 0
    queued = 0
    for ref in connector.discover():
        discovered += 1
        if known.get(ref.source_id) == ref.content_hash:
            continue
        ingest_document.delay(source_uuid, ref.model_dump(mode="json"))
        queued += 1
    return {"discovered": discovered, "queued": queued, "skipped": discovered - queued}


@app.task(name="kos.ingest_document")
def ingest_document(source_uuid: str, ref_payload: dict[str, Any]) -> dict[str, Any]:
    """Blob a MinIO → pipeline s1-s3 → Postgres → eventos del bus."""
    settings = get_settings()
    ref = SourceRef.model_validate(ref_payload)
    source = asyncio.run(_load_source(uuid.UUID(source_uuid), settings))
    if source is None:
        raise ValueError(f"Fuente {source_uuid} no registrada")

    connector = _build_connector(source)
    raw = connector.fetch(ref)

    doc_id = make_doc_id(raw.connector, raw.source_id)
    blob = raw.content.encode("utf-8") if isinstance(raw.content, str) else raw.content
    minio_client = minio_storage.create_client(settings)
    minio_storage.put_blob(
        minio_client,
        settings.minio_bucket,
        f"{raw.connector}/{doc_id}/{ref.content_hash}",
        blob,
        content_type=raw.mime_type,
    )

    parsed = run_pipeline(raw)

    async def _persist() -> int:
        engine = create_engine(settings)
        try:
            return await upsert_parsed_document(
                engine,
                parsed,
                connector=raw.connector,
                source_id=raw.source_id,
                fetched_at=raw.fetched_at,
                content_hash=ref.content_hash,
                source_uuid=uuid.UUID(source_uuid),
            )
        finally:
            await engine.dispose()

    chunk_count = asyncio.run(_persist())

    redis_client = redis_storage.create_sync_client(settings)
    try:
        redis_storage.publish_event_sync(
            redis_client,
            DocumentIngested(
                doc_id=parsed.doc_id,
                connector=raw.connector,
                source_id=raw.source_id,
                content_hash=ref.content_hash,
            ),
        )
        redis_storage.publish_event_sync(
            redis_client,
            DocumentParsed(doc_id=parsed.doc_id, pipeline_version=PIPELINE_VERSION),
        )
    finally:
        redis_client.close()

    # Etapa cara aparte (doc 05 §3): los embeddings van por lotes en su propia task.
    embed_document.delay(str(parsed.doc_id))

    return {"doc_id": str(parsed.doc_id), "chunks": chunk_count}
