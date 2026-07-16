"""Tablas iniciales de documentos y chunks (Sprint 1, doc 02 §2).

Revision ID: 0001
Revises:
Create Date: 2026-07-13

"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

EMBEDDING_DIM = 1024  # bge-m3


def upgrade() -> None:
    # init.sql ya la crea; por si la BD no nació del compose.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("doc_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("connector", sa.Text, nullable=False),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("summary", sa.Text),
        sa.Column("author", sa.Text),
        sa.Column("language", sa.Text),
        sa.Column("keywords", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("links", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("confidence", sa.Float, nullable=False, server_default=sa.text("1.0")),
        sa.Column("content_hash", sa.Text),
        sa.Column("source_metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("modified_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("connector", "source_id", name="uq_documents_connector_source"),
    )

    op.create_table(
        "chunks",
        sa.Column("chunk_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "doc_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.doc_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("start_offset", sa.Integer),
        sa.Column("end_offset", sa.Integer),
        sa.Column("embedding", Vector(EMBEDDING_DIM)),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_chunks_doc_id", "chunks", ["doc_id"])
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("chunks")
    op.drop_table("documents")
