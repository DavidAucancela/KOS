"""Cliente de PostgreSQL + pgvector y esquema de tablas de documentos/chunks.

El esquema se versiona con Alembic (`kos_core/alembic/`), único dueño del
esquema (doc 10 §9); estas Table son la referencia para leer/escribir.
"""

from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime

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
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

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
    Column("keywords", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("links", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("confidence", Float, nullable=False, server_default=text("1.0")),
    Column("content_hash", Text),
    Column("source_metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("created_at", DateTime(timezone=True)),
    Column("modified_at", DateTime(timezone=True)),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
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
