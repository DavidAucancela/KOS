"""Tasks de ingesta (Sprint 2, doc 05): fuente → conector → parser → almacenes.

`kos.sync_source` descubre los documentos de una fuente registrada y encola
`kos.ingest_document` por cada uno cuyo `content_hash` cambió (idempotencia,
doc 05 §5). La ingesta guarda el blob original en MinIO (inmutable), persiste
el `ParsedDocument` en Postgres y emite los eventos del bus (doc 06 §3).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from sqlalchemy import select

from kos_connectors.base import Connector, SourceRef
from kos_connectors.registry import get_connector
from kos_core.config import Settings, get_settings
from kos_core.observability import (
    documents_ingested_total,
    documents_retired_total,
    pipeline_duration_seconds,
)
from kos_core.schemas import make_doc_id
from kos_core.schemas.events import DocumentDeleted, DocumentIngested, DocumentParsed
from kos_core.storage import minio as minio_storage
from kos_core.storage import redis as redis_storage
from kos_core.storage.postgres import (
    create_engine,
    documents_table,
    retire_documents,
    sources_table,
    upsert_parsed_document,
)
from kos_workers.celery_app import app
from kos_workers.pipeline import PIPELINE_VERSION, run_pipeline
from kos_workers.tasks.embed import embed_document
from kos_workers.tasks.graph_retire import graph_retire_document
from kos_workers.tasks.memory_retire import memory_retire_document


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


async def _known_hashes(
    source_uuid: uuid.UUID, connector_name: str, settings: Settings
) -> dict[str, str]:
    """content_hash registrado por source_id (no tombstone), para saltar sin cambios.

    Filtrado por `source_uuid` además de `connector` (doc 05 §5): dos fuentes
    distintas pueden compartir conector (ej. dos vaults "obsidian"), y sin este
    filtro los documentos de una fuente se confunden con los de otra —
    `sync_source`/`kos reindex` sobre una fuente pequeña llegaría a marcar como
    "borrados" (tombstone) los documentos de una fuente ajena más grande.
    """
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                select(documents_table.c.source_id, documents_table.c.content_hash).where(
                    documents_table.c.connector == connector_name,
                    documents_table.c.source_uuid == source_uuid,
                    documents_table.c.deleted_at.is_(None),
                )
            )
            return {row.source_id: row.content_hash for row in result if row.content_hash}
    finally:
        await engine.dispose()


async def _retire_missing(
    source_uuid: uuid.UUID, connector_name: str, discovered_ids: set[str], settings: Settings
) -> list[uuid.UUID]:
    """Tombstone de los documentos conocidos que ya no aparecen en discover() (doc 05 §5)."""
    known = await _known_hashes(source_uuid, connector_name, settings)
    missing = set(known) - discovered_ids
    if not missing:
        return []
    engine = create_engine(settings)
    try:
        retired = await retire_documents(
            engine, source_uuid=source_uuid, connector=connector_name, source_ids=missing
        )
    finally:
        await engine.dispose()
    if retired:
        documents_retired_total.labels(connector=connector_name).inc(len(retired))
    return retired


def _build_connector(source: dict[str, Any]) -> Connector:
    config: dict[str, Any] = source.get("config") or {}
    return get_connector(str(source["connector"]), **config)


@app.task(name="kos.sync_source")
def sync_source(source_uuid: str, force: bool = False) -> dict[str, int]:
    """Descubre la fuente, encola lo nuevo/cambiado y retira lo borrado (doc 05 §5).

    `force=True` (usado por `kos reindex`) ignora los hashes conocidos y
    reencola todo lo descubierto, para reconstruir los derivados desde
    MinIO + la fuente sin depender de que algo haya cambiado.
    """
    settings = get_settings()
    source = asyncio.run(_load_source(uuid.UUID(source_uuid), settings))
    if source is None or not source["enabled"]:
        return {"discovered": 0, "queued": 0, "skipped": 0, "retired": 0}

    source_uuid_value = uuid.UUID(source_uuid)
    connector = _build_connector(source)
    known = {} if force else asyncio.run(_known_hashes(source_uuid_value, connector.name, settings))

    discovered = 0
    queued = 0
    discovered_ids: set[str] = set()
    for ref in connector.discover():
        discovered += 1
        discovered_ids.add(ref.source_id)
        if known.get(ref.source_id) == ref.content_hash:
            continue
        ingest_document.delay(source_uuid, ref.model_dump(mode="json"))
        queued += 1
    retired = asyncio.run(
        _retire_missing(source_uuid_value, connector.name, discovered_ids, settings)
    )
    if retired:
        redis_client = redis_storage.create_sync_client(settings)
        try:
            for doc_id in retired:
                redis_storage.publish_event_sync(redis_client, DocumentDeleted(doc_id=doc_id))
        finally:
            redis_client.close()
        # Propaga el tombstone al grafo y a memoria (doc 05 §5, doc 06 §3, doc 04
        # §5): mismo patrón de encadenado directo que `embed_document.delay`/
        # `graph_sync.delay`, no una suscripción al evento recién publicado (ese
        # evento es para Aprendizaje/Recomendador, que todavía no existen).
        for doc_id in retired:
            graph_retire_document.delay(str(doc_id))
            memory_retire_document.delay(str(doc_id))
    return {
        "discovered": discovered,
        "queued": queued,
        "skipped": discovered - queued,
        "retired": len(retired),
    }


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
    if raw.raw_bytes is not None:
        blob = raw.raw_bytes
    else:
        blob = raw.content.encode("utf-8") if isinstance(raw.content, str) else raw.content
    minio_client = minio_storage.create_client(settings)
    minio_storage.put_blob(
        minio_client,
        settings.minio_bucket,
        f"{raw.connector}/{doc_id}/{ref.content_hash}",
        blob,
        content_type=raw.mime_type,
    )

    pipeline_started = time.perf_counter()
    parsed = run_pipeline(raw)
    pipeline_duration_seconds.labels(connector=raw.connector).observe(
        time.perf_counter() - pipeline_started
    )

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

    documents_ingested_total.labels(connector=raw.connector).inc()
    return {"doc_id": str(parsed.doc_id), "chunks": chunk_count}


async def _enabled_source_uuids(settings: Settings) -> list[uuid.UUID]:
    engine = create_engine(settings)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                select(sources_table.c.source_uuid).where(sources_table.c.enabled.is_(True))
            )
            return [row.source_uuid for row in result]
    finally:
        await engine.dispose()


@app.task(name="kos.sync_all_sources")
def sync_all_sources() -> dict[str, int]:
    """Polling programado (doc 05 §2, Celery beat): sincroniza toda fuente habilitada.

    Barato si nada cambió: `sync_source` compara por `content_hash` y solo
    reencola lo distinto (doc 05 §5).
    """
    settings = get_settings()
    source_uuids = asyncio.run(_enabled_source_uuids(settings))
    for source_uuid in source_uuids:
        sync_source.delay(str(source_uuid))
    return {"sources": len(source_uuids)}
