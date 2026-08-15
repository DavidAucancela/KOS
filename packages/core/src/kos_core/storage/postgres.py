"""Cliente de PostgreSQL + pgvector y esquema de tablas de documentos/chunks.

El esquema se versiona con Alembic (`kos_core/alembic/`), único dueño del
esquema (doc 10 §9); estas Table son la referencia para leer/escribir.
"""

from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from kos_core.confidence import ALIAS_BOOST
from kos_core.config import Settings
from kos_core.schemas.documents import ParsedDocument

EMBEDDING_DIM = 1024  # dimensión de bge-m3

metadata = MetaData()

sources_table = Table(
    "sources",
    metadata,
    Column("source_uuid", UUID(as_uuid=True), primary_key=True),
    Column("name", Text, nullable=False, unique=True),
    Column("connector", Text, nullable=False),
    Column("config", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("enabled", Boolean, nullable=False, server_default=text("true")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

documents_table = Table(
    "documents",
    metadata,
    Column("doc_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "source_uuid",
        UUID(as_uuid=True),
        ForeignKey("sources.source_uuid", ondelete="SET NULL"),
        index=True,
    ),
    Column("connector", Text, nullable=False),
    Column("source_id", Text, nullable=False),
    Column("title", Text),
    Column("summary", Text),
    Column("author", Text),
    Column("language", Text),
    Column("doc_type", Text, nullable=False, server_default=text("'content'"), index=True),
    Column("keywords", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("links", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("confidence", Float, nullable=False, server_default=text("1.0")),
    Column("content_hash", Text),
    Column("source_metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True)),
    Column("modified_at", DateTime(timezone=True)),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True)),
    UniqueConstraint("connector", "source_id", name="uq_documents_connector_source"),
)

chunks_table = Table(
    "chunks",
    metadata,
    Column("chunk_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "doc_id",
        UUID(as_uuid=True),
        ForeignKey("documents.doc_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("text", Text, nullable=False),
    Column("position", Integer, nullable=False),
    Column("start_offset", Integer),
    Column("end_offset", Integer),
    Column("embedding", Vector(EMBEDDING_DIM)),
    Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
)

memory_items_table = Table(
    "memory_items",
    metadata,
    Column("memory_id", UUID(as_uuid=True), primary_key=True),
    Column("type", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("embedding", Vector(EMBEDDING_DIM)),
    Column("entities", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("sources", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("confidence", Float, nullable=False, server_default=text("1.0")),
    Column("salience", Float, nullable=False, server_default=text("0.5")),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_accessed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("archived_at", DateTime(timezone=True)),
    Column(
        "superseded_by",
        UUID(as_uuid=True),
        ForeignKey("memory_items.memory_id", ondelete="SET NULL"),
    ),
)


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(settings.postgres_dsn, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def ping(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def upsert_parsed_document(
    engine: AsyncEngine,
    parsed: ParsedDocument,
    *,
    connector: str,
    source_id: str,
    fetched_at: datetime,
    content_hash: str | None = None,
    source_uuid: uuid_lib.UUID | None = None,
) -> int:
    """Persiste un ParsedDocument de forma idempotente (doc 05 §6).

    Estrategia Sprint 2: delete + insert por doc_id (el diff de chunks para
    re-embeds parciales llega con la reingesta incremental, Sprint 5).
    Devuelve el número de chunks guardados. `body` no se persiste (el original
    vive en MinIO; el texto consultable, en los chunks).
    """
    # Los campos JSONB deben ser JSON-serializables: el frontmatter puede traer
    # date/datetime de YAML y el driver no los convierte solo.
    json_safe = parsed.model_dump(mode="json", include={"keywords", "links", "source_metadata"})
    async with engine.begin() as conn:
        await conn.execute(
            documents_table.delete().where(documents_table.c.doc_id == parsed.doc_id)
        )
        await conn.execute(
            documents_table.insert().values(
                doc_id=parsed.doc_id,
                source_uuid=source_uuid,
                connector=connector,
                source_id=source_id,
                title=parsed.title,
                summary=parsed.summary,
                author=parsed.author,
                language=parsed.language,
                doc_type=parsed.doc_type,
                keywords=json_safe["keywords"],
                links=json_safe["links"],
                confidence=parsed.confidence,
                content_hash=content_hash,
                source_metadata=json_safe["source_metadata"],
                created_at=parsed.created_at,
                modified_at=parsed.modified_at,
                fetched_at=fetched_at,
            )
        )
        if parsed.chunks:
            await conn.execute(
                chunks_table.insert(),
                [
                    {
                        "chunk_id": chunk.chunk_id,
                        "doc_id": chunk.doc_id,
                        "text": chunk.text,
                        "position": chunk.position.order,
                        "start_offset": chunk.position.start,
                        "end_offset": chunk.position.end,
                        "embedding": chunk.embedding,
                        "metadata": chunk.model_dump(mode="json")["metadata"],
                    }
                    for chunk in parsed.chunks
                ],
            )
    return len(parsed.chunks)


async def retire_documents(
    engine: AsyncEngine, *, source_uuid: uuid_lib.UUID, connector: str, source_ids: set[str]
) -> list[uuid_lib.UUID]:
    """Marca tombstone (doc 05 §5) y retira los chunks de documentos ausentes en la fuente.

    Filtrado por `source_uuid` además de `connector`: dos fuentes distintas pueden
    compartir conector (ej. dos vaults "obsidian"), y sin este filtro se
    retirarían por error documentos de una fuente ajena que comparte conector.
    El blob original sigue en MinIO (inmutable); solo se retira la evidencia
    consultable (chunks) y se registra `deleted_at`. Devuelve los `doc_id`
    retirados (antes solo la cantidad; Sprint 11 los necesita para propagar el
    tombstone al grafo, uno por uno, vía `kos.graph_retire_document`).
    """
    if not source_ids:
        return []
    async with engine.begin() as conn:
        rows = (
            (
                await conn.execute(
                    select(documents_table.c.doc_id).where(
                        documents_table.c.connector == connector,
                        documents_table.c.source_uuid == source_uuid,
                        documents_table.c.source_id.in_(source_ids),
                        documents_table.c.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            return []
        await conn.execute(chunks_table.delete().where(chunks_table.c.doc_id.in_(rows)))
        await conn.execute(
            documents_table.update()
            .where(documents_table.c.doc_id.in_(rows))
            .values(deleted_at=func.now())
        )
        return list(rows)


async def insert_memory(
    engine: AsyncEngine,
    *,
    memory_id: uuid_lib.UUID,
    type: str,
    content: str,
    embedding: list[float] | None,
    entities: list[str],
    sources: list[dict[str, Any]],
    confidence: float,
    salience: float,
) -> None:
    """Escribe una `MemoryItem` (doc 04 §2); `kos.memory_learn`/`kos.memory_consolidate`
    son los únicos llamadores (v0.4 como pipeline fijo, doc 04 §1.1). `sources` es
    JSONB de pares `{doc_id, confidence}` (doc 04 §5, decidido 2026-08-13; antes
    lista plana de `doc_id`) — quien llama ya arma cada par, esto solo persiste."""
    async with engine.begin() as conn:
        await conn.execute(
            memory_items_table.insert().values(
                memory_id=memory_id,
                type=type,
                content=content,
                embedding=embedding,
                entities=entities,
                sources=sources,
                confidence=confidence,
                salience=salience,
            )
        )


# Columnas de auditoría (doc 06 §2 `GET /v1/memory`): sin `embedding` — 1024
# floats que ningún consumidor de la API necesita ver, solo pesan la respuesta.
_MEMORY_COLUMNS = [
    memory_items_table.c.memory_id,
    memory_items_table.c.type,
    memory_items_table.c.content,
    memory_items_table.c.entities,
    memory_items_table.c.sources,
    memory_items_table.c.confidence,
    memory_items_table.c.salience,
    memory_items_table.c.created_at,
    memory_items_table.c.last_accessed_at,
    memory_items_table.c.archived_at,
    memory_items_table.c.superseded_by,
]


async def get_memory(engine: AsyncEngine, memory_id: uuid_lib.UUID) -> dict[str, Any] | None:
    async with engine.connect() as conn:
        row = (
            (
                await conn.execute(
                    select(*_MEMORY_COLUMNS).where(memory_items_table.c.memory_id == memory_id)
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None


async def list_memories(
    engine: AsyncEngine,
    *,
    type: str | None = None,
    q: str | None = None,
    cursor: uuid_lib.UUID | None = None,
    limit: int = 20,
    include_archived: bool = False,
) -> tuple[list[dict[str, Any]], uuid_lib.UUID | None]:
    """Auditoría de memoria (doc 06 §2 `GET /v1/memory?type=&q=`).

    `q` es un filtro de texto simple (`ILIKE` sobre `content`), no búsqueda
    semántica — alcanzaba para auditar sin sumar una dependencia del embedder
    a un endpoint de solo lectura; búsqueda semántica sobre memoria queda para
    cuando `/v1/query` de verdad la consuma (deuda visible, doc 04 §3 paso 3).
    """
    query = select(*_MEMORY_COLUMNS).order_by(memory_items_table.c.memory_id).limit(limit)
    if not include_archived:
        query = query.where(memory_items_table.c.archived_at.is_(None))
    if type is not None:
        query = query.where(memory_items_table.c.type == type)
    if q is not None:
        query = query.where(memory_items_table.c.content.ilike(f"%{q}%"))
    if cursor is not None:
        query = query.where(memory_items_table.c.memory_id > cursor)
    async with engine.connect() as conn:
        rows = [dict(row) for row in (await conn.execute(query)).mappings().all()]
    next_cursor = rows[-1]["memory_id"] if len(rows) == limit else None
    return rows, next_cursor


async def archive_memory(engine: AsyncEngine, memory_id: uuid_lib.UUID) -> bool:
    """'Olvidar' (doc 06 §2 `DELETE /v1/memory/{id}`): archivado, nunca borrado
    físico (doc 04 §3: 'nada se borra sin pasar por estado archivado')."""
    async with engine.begin() as conn:
        result = await conn.execute(
            memory_items_table.update()
            .where(
                memory_items_table.c.memory_id == memory_id,
                memory_items_table.c.archived_at.is_(None),
            )
            .values(archived_at=func.now())
        )
        return result.rowcount > 0


async def list_unconsolidated_episodic(engine: AsyncEngine) -> list[dict[str, Any]]:
    """Memorias episódicas activas con embedding, candidatas de `kos.memory_consolidate`
    (doc 04 §3 paso 2): ni archivadas ni ya fusionadas en una semántica anterior."""
    query = select(memory_items_table).where(
        memory_items_table.c.type == "episodic",
        memory_items_table.c.archived_at.is_(None),
        memory_items_table.c.superseded_by.is_(None),
        memory_items_table.c.embedding.is_not(None),
    )
    async with engine.connect() as conn:
        return [dict(row) for row in (await conn.execute(query)).mappings().all()]


async def retire_memory_sources(engine: AsyncEngine, doc_id: str) -> dict[str, int]:
    """Contraparte de `retire_document` (Neo4j) para memoria (doc 04 §5, Sprint 14):
    saca `doc_id` de `sources[]` de las memorias activas que lo mencionan y
    recalcula `confidence` con lo que sobrevive — misma fórmula que el grafo,
    `min(1.0, max(confidence base restante) + ALIAS_BOOST x (n_restantes - 1))`.
    Memoria no tiene `locked` (no hay corrección manual de memoria todavía, doc
    04 §2): siempre se recalcula. Sin ninguna fuente restante, se archiva en vez
    de recalcular (doc 04 §3: nada se borra sin pasar por archivado)."""
    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                select(memory_items_table.c.memory_id, memory_items_table.c.sources).where(
                    memory_items_table.c.archived_at.is_(None),
                    memory_items_table.c.sources.contains([{"doc_id": doc_id}]),
                )
            )
        ).all()
        archived = 0
        recalculated = 0
        for memory_id, sources in rows:
            remaining = [s for s in sources if s["doc_id"] != doc_id]
            if not remaining:
                await conn.execute(
                    memory_items_table.update()
                    .where(memory_items_table.c.memory_id == memory_id)
                    .values(sources=remaining, archived_at=func.now())
                )
                archived += 1
                continue
            new_confidence = min(
                1.0,
                max(s["confidence"] for s in remaining) + ALIAS_BOOST * (len(remaining) - 1),
            )
            await conn.execute(
                memory_items_table.update()
                .where(memory_items_table.c.memory_id == memory_id)
                .values(sources=remaining, confidence=new_confidence)
            )
            recalculated += 1
    return {"recalculated": recalculated, "archived": archived}


async def mark_superseded(
    engine: AsyncEngine, memory_ids: list[uuid_lib.UUID], *, superseded_by: uuid_lib.UUID
) -> int:
    """Marca memorias episódicas como fusionadas en la semántica `superseded_by`
    (doc 04 §3 paso 5): no se borran, quedan auditables."""
    if not memory_ids:
        return 0
    async with engine.begin() as conn:
        result = await conn.execute(
            memory_items_table.update()
            .where(memory_items_table.c.memory_id.in_(memory_ids))
            .values(superseded_by=superseded_by)
        )
        return result.rowcount
