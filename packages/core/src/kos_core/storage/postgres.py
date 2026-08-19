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
from kos_core.schemas.plan import Plan

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
    Column("entity_node_ids", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
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

recommendations_table = Table(
    "recommendations",
    metadata,
    Column("recommendation_id", UUID(as_uuid=True), primary_key=True),
    Column("type", Text, nullable=False, index=True),
    Column("title", Text, nullable=False),
    Column("description", Text, nullable=False, server_default=text("''")),
    Column("evidence", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("target_entities", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("confidence", Float, nullable=False, server_default=text("0.0")),
    Column("priority", Integer, nullable=False, server_default=text("0")),
    Column("status", Text, nullable=False, server_default=text("'pending'"), index=True),
    Column("dismissed_reason", Text),
    Column("source_event_id", Text),
    Column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    ),
    Column("resolved_at", DateTime(timezone=True)),
)

node_embeddings_table = Table(
    "node_embeddings",
    metadata,
    Column("node_id", Text, primary_key=True),
    Column("canonical_name", Text, nullable=False),
    Column("node_type", Text, nullable=False, index=True),
    Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

plans_table = Table(
    "plans",
    metadata,
    Column("plan_id", UUID(as_uuid=True), primary_key=True),
    Column("query", Text, nullable=False),
    Column("steps", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("post", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    Column("degraded", Boolean, nullable=False, server_default=text("false")),
    Column("degraded_reason", Text),
    Column("elapsed_ms", Float, nullable=False, server_default=text("0")),
    Column("trace_id", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
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


# Columnas de auditoría de `GET /v1/documents/{id}` (doc 06 §2): sin `body` (no
# se persiste, vive en MinIO — el texto consultable está en los chunks).
_DOCUMENT_COLUMNS = [
    documents_table.c.doc_id,
    documents_table.c.source_uuid,
    documents_table.c.connector,
    documents_table.c.source_id,
    documents_table.c.title,
    documents_table.c.summary,
    documents_table.c.author,
    documents_table.c.language,
    documents_table.c.keywords,
    documents_table.c.links,
    documents_table.c.confidence,
    documents_table.c.content_hash,
    documents_table.c.created_at,
    documents_table.c.modified_at,
    documents_table.c.fetched_at,
    documents_table.c.deleted_at,
]


async def get_document(engine: AsyncEngine, doc_id: uuid_lib.UUID) -> dict[str, Any] | None:
    """Promovido a core en Sprint 16 (antes en `apps/api/.../document_service.py`)
    para que `GET /v1/documents/{id}` y la herramienta MCP `docs.read_document`
    compartan el mismo mapeo."""
    query = select(*_DOCUMENT_COLUMNS, documents_table.c.source_metadata).where(
        documents_table.c.doc_id == doc_id
    )
    async with engine.connect() as conn:
        row = (await conn.execute(query)).mappings().first()
        return dict(row) if row else None


async def list_chunks(
    engine: AsyncEngine, doc_id: uuid_lib.UUID, *, cursor: int | None, limit: int
) -> tuple[list[dict[str, Any]], int | None]:
    """Chunks de un documento en orden; el cursor es la última `position` vista.
    Promovido a core en Sprint 16 (antes en `apps/api/.../document_service.py`)
    para que `GET /v1/documents/{id}/chunks` y `docs.read_document` (MCP)
    compartan el mismo mapeo — el cuerpo de un documento se reconstruye
    concatenando chunks, no hay un `body` crudo persistido en Postgres."""
    query = (
        select(
            chunks_table.c.chunk_id,
            chunks_table.c.doc_id,
            chunks_table.c.text,
            chunks_table.c.position,
            chunks_table.c.start_offset,
            chunks_table.c.end_offset,
            chunks_table.c.metadata,
            chunks_table.c.embedding.is_not(None).label("has_embedding"),
        )
        .where(chunks_table.c.doc_id == doc_id)
        .order_by(chunks_table.c.position)
        .limit(limit)
    )
    if cursor is not None:
        query = query.where(chunks_table.c.position > cursor)
    async with engine.connect() as conn:
        rows = [dict(row) for row in (await conn.execute(query)).mappings().all()]
    next_cursor = int(rows[-1]["position"]) if len(rows) == limit else None
    return rows, next_cursor


async def get_chunk(engine: AsyncEngine, chunk_id: uuid_lib.UUID) -> dict[str, Any] | None:
    """Un chunk individual con `embedding`/`entity_node_ids` (doc 12 §4): la
    task de relaciones cross-documento re-carga chunks por id en una corrida
    separada de la que los generó, no hay lista en memoria que reusar."""
    query = select(
        chunks_table.c.chunk_id,
        chunks_table.c.doc_id,
        chunks_table.c.text,
        chunks_table.c.embedding,
        chunks_table.c.entity_node_ids,
    ).where(chunks_table.c.chunk_id == chunk_id)
    async with engine.connect() as conn:
        row = (await conn.execute(query)).mappings().first()
        return dict(row) if row else None


async def set_chunk_entity_node_ids(
    engine: AsyncEngine, chunk_id: uuid_lib.UUID, node_ids: list[str]
) -> None:
    """Persiste qué nodos de Neo4j salieron de este chunk (doc 12 §4) — se
    llama al final de cada `graph_sync`, para que una corrida posterior de
    relaciones cross-documento sepa, dado el chunk_id de OTRO documento, a
    qué entidades ya resueltas corresponde."""
    async with engine.begin() as conn:
        await conn.execute(
            chunks_table.update()
            .where(chunks_table.c.chunk_id == chunk_id)
            .values(entity_node_ids=node_ids)
        )


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


async def insert_recommendation(
    engine: AsyncEngine,
    *,
    recommendation_id: uuid_lib.UUID,
    type: str,
    title: str,
    description: str,
    evidence: list[dict[str, Any]],
    target_entities: list[str],
    confidence: float,
    priority: int,
    status: str,
    source_event_id: str | None,
) -> None:
    """Escribe una `Recommendation` (doc 11 §2/§6, Sprint 22); `recommendations.store`
    (MCP) es el único llamador — el `RecommenderAgent` nunca importa esto
    directo (ADR-0005: los agentes solo hablan MCP)."""
    async with engine.begin() as conn:
        await conn.execute(
            recommendations_table.insert().values(
                recommendation_id=recommendation_id,
                type=type,
                title=title,
                description=description,
                evidence=evidence,
                target_entities=target_entities,
                confidence=confidence,
                priority=priority,
                status=status,
                source_event_id=source_event_id,
            )
        )


async def recent_seed_chunks(engine: AsyncEngine, *, limit: int) -> list[dict[str, Any]]:
    """Chunks recientes con embedding real, para sembrar candidatos de
    contradicción (Sprint 24, doc 11 §4) — devuelve `embedding` como
    `list[float]` real (vía el tipo `Vector` de la columna, no SQL textual,
    que no deserializa el vector de vuelta a Python). No acotado por el
    disparo real (`node_ids`/`relation_ids`) que debounceó — misma deuda
    documentada que `gaps_by_prerequisite` (Sprint 23)."""
    query = (
        select(
            chunks_table.c.chunk_id,
            chunks_table.c.doc_id,
            chunks_table.c.text,
            chunks_table.c.embedding,
            documents_table.c.title,
        )
        .select_from(
            chunks_table.join(documents_table, documents_table.c.doc_id == chunks_table.c.doc_id)
        )
        .where(chunks_table.c.embedding.is_not(None))
        .order_by(documents_table.c.created_at.desc(), chunks_table.c.position.asc())
        .limit(limit)
    )
    async with engine.connect() as conn:
        return [dict(row) for row in (await conn.execute(query)).mappings().all()]


def _format_vector(values: list[float]) -> str:
    """Literal pgvector: '[v1,v2,...]' (mismo formato que `search.py::_format_vector`,
    duplicado acá para no crear un import cruzado solo por una función de 1 línea)."""
    return "[" + ",".join(repr(float(value)) for value in values) + "]"


async def upsert_node_embedding(
    engine: AsyncEngine,
    *,
    node_id: str,
    canonical_name: str,
    node_type: str,
    embedding: list[float],
) -> None:
    """Persiste el embedding de un nodo del grafo (doc 12 §3) — se llama en el
    mismo commit que `merge_node` escribe/actualiza el nodo en Neo4j, para que
    la resolución de entidades indexada (`similar_nodes`) tenga cobertura
    completa sin re-embedear en cada llamada."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO node_embeddings
                    (node_id, canonical_name, node_type, embedding, updated_at)
                VALUES (:node_id, :canonical_name, :node_type, CAST(:embedding AS vector), now())
                ON CONFLICT (node_id) DO UPDATE SET
                    canonical_name = EXCLUDED.canonical_name,
                    node_type = EXCLUDED.node_type,
                    embedding = EXCLUDED.embedding,
                    updated_at = now()
                """
            ),
            {
                "node_id": node_id,
                "canonical_name": canonical_name,
                "node_type": node_type,
                "embedding": _format_vector(embedding),
            },
        )


_SIMILAR_NODES_SQL = text(
    """
    SELECT node_id, canonical_name, node_type,
           1 - (embedding <=> CAST(:qvec AS vector)) AS score
    FROM node_embeddings
    WHERE node_type = :node_type
      AND 1 - (embedding <=> CAST(:qvec AS vector)) >= :floor
    ORDER BY score DESC, node_id
    LIMIT :limit
    """
)


async def similar_nodes(
    engine: AsyncEngine,
    embedding: list[float],
    *,
    node_type: str,
    floor: float,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Candidatos de resolución de entidades (doc 12 §3): búsqueda ANN indexada
    (índice HNSW, migración 0010) contra los embeddings de nodo ya persistidos,
    reemplazando el loop de coseno en memoria de `graph_sync.py::_resolve_entity`
    sobre *todos* los nodos existentes de ese tipo. `floor` es una banda amplia
    para generar candidatos (el veredicto final lo da el LLM, no este score
    solo) — mismo principio que `search.py::similarity_band_chunks`."""
    params = {
        "qvec": _format_vector(embedding),
        "node_type": node_type,
        "floor": floor,
        "limit": limit,
    }
    async with engine.connect() as conn:
        result = await conn.execute(_SIMILAR_NODES_SQL, params)
        rows = result.mappings().all()
    return [dict(row) for row in rows]


async def has_active_recommendation(
    engine: AsyncEngine, *, type: str, target_entities: list[str]
) -> bool:
    """Guardarraíl contra duplicados (Sprint 23) y contra reaparición
    inmediata tras un descarte (Sprint 25, doc 11 §8): bloquea la
    regeneración mientras exista cualquier recomendación con la misma firma
    (`type` + `target_entities`) en estado `pending`, `accepted` o
    `dismissed` — solo `expired`/`superseded` no bloquean. Antes de Sprint 25
    (`has_pending_recommendation`) solo miraba `pending`; un descarte dejaba
    la firma libre para que la siguiente pasada la volviera a proponer."""
    sorted_entities = sorted(target_entities)
    query = select(recommendations_table.c.recommendation_id).where(
        recommendations_table.c.status.in_(["pending", "accepted", "dismissed"]),
        recommendations_table.c.type == type,
        recommendations_table.c.target_entities == sorted_entities,
    )
    async with engine.connect() as conn:
        return (await conn.execute(query)).first() is not None


async def update_recommendation_status(
    engine: AsyncEngine,
    recommendation_id: uuid_lib.UUID,
    *,
    status: str,
    dismissed_reason: str | None,
) -> dict[str, Any] | None:
    """`PATCH /v1/recommendations/{id}` (doc 06 §2, doc 11 §8, Sprint 25):
    aceptar/descartar. Fija `resolved_at`; solo actúa sobre recomendaciones
    todavía `pending` (idempotente contra doble-click, no reescribe una ya
    resuelta) — mismo criterio que `archive_memory` (no reabre lo ya
    archivado)."""
    async with engine.begin() as conn:
        result = await conn.execute(
            recommendations_table.update()
            .where(
                recommendations_table.c.recommendation_id == recommendation_id,
                recommendations_table.c.status == "pending",
            )
            .values(status=status, dismissed_reason=dismissed_reason, resolved_at=func.now())
        )
        if result.rowcount == 0:
            return None
        row = (
            (
                await conn.execute(
                    select(*_RECOMMENDATION_COLUMNS).where(
                        recommendations_table.c.recommendation_id == recommendation_id
                    )
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row is not None else None


_RECOMMENDATION_COLUMNS = [
    recommendations_table.c.recommendation_id,
    recommendations_table.c.type,
    recommendations_table.c.title,
    recommendations_table.c.description,
    recommendations_table.c.evidence,
    recommendations_table.c.target_entities,
    recommendations_table.c.confidence,
    recommendations_table.c.priority,
    recommendations_table.c.status,
    recommendations_table.c.dismissed_reason,
    recommendations_table.c.source_event_id,
    recommendations_table.c.created_at,
    recommendations_table.c.resolved_at,
]


async def list_recommendations(
    engine: AsyncEngine,
    *,
    type: str | None = None,
    status: str | None = None,
    cursor: uuid_lib.UUID | None = None,
    limit: int = 20,
) -> tuple[list[dict[str, Any]], uuid_lib.UUID | None]:
    """`GET /v1/recommendations?type=&status=` (doc 06 §2, Sprint 23) — mismo
    patrón de cursor que `list_memories`."""
    query = (
        select(*_RECOMMENDATION_COLUMNS)
        .order_by(recommendations_table.c.recommendation_id)
        .limit(limit)
    )
    if type is not None:
        query = query.where(recommendations_table.c.type == type)
    if status is not None:
        query = query.where(recommendations_table.c.status == status)
    if cursor is not None:
        query = query.where(recommendations_table.c.recommendation_id > cursor)
    async with engine.connect() as conn:
        rows = [dict(row) for row in (await conn.execute(query)).mappings().all()]
    next_cursor = rows[-1]["recommendation_id"] if len(rows) == limit else None
    return rows, next_cursor


async def insert_plan(engine: AsyncEngine, plan: Plan) -> None:
    """Persiste un `Plan` ya ejecutado (doc 03 §3 regla 3, Sprint 19) — escritura
    síncrona desde `query_service.answer_query`, no un job en background: el
    caller necesita `plan.plan_id` consultable de inmediato vía
    `GET /v1/plans/{id}`, sin condición de carrera."""
    async with engine.begin() as conn:
        await conn.execute(
            plans_table.insert().values(
                plan_id=plan.plan_id,
                query=plan.query,
                steps=[step.model_dump(mode="json") for step in plan.steps],
                post=[step.model_dump(mode="json") for step in plan.post],
                degraded=plan.degraded,
                degraded_reason=plan.degraded_reason,
                elapsed_ms=plan.elapsed_ms,
                trace_id=plan.trace_id,
                created_at=plan.created_at,
            )
        )


_PLAN_COLUMNS = [
    plans_table.c.plan_id,
    plans_table.c.query,
    plans_table.c.steps,
    plans_table.c.post,
    plans_table.c.degraded,
    plans_table.c.degraded_reason,
    plans_table.c.elapsed_ms,
    plans_table.c.trace_id,
    plans_table.c.created_at,
]


async def get_plan(engine: AsyncEngine, plan_id: uuid_lib.UUID) -> dict[str, Any] | None:
    async with engine.connect() as conn:
        row = (
            (await conn.execute(select(*_PLAN_COLUMNS).where(plans_table.c.plan_id == plan_id)))
            .mappings()
            .first()
        )
        return dict(row) if row else None
