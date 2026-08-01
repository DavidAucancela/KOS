"""Tabla memory_items (Sprint 12, doc 04 §2, v0.4 Memoria y aprendizaje).

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-31

"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None

EMBEDDING_DIM = 1024  # bge-m3


def upgrade() -> None:
    op.create_table(
        "memory_items",
        sa.Column("memory_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM)),
        sa.Column("entities", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sources", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("confidence", sa.Float, nullable=False, server_default=sa.text("1.0")),
        sa.Column("salience", sa.Float, nullable=False, server_default=sa.text("0.5")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_accessed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column(
            "superseded_by",
            UUID(as_uuid=True),
            sa.ForeignKey("memory_items.memory_id", ondelete="SET NULL"),
        ),
    )
    op.create_index("ix_memory_items_type", "memory_items", ["type"])
    op.execute(
        "CREATE INDEX ix_memory_items_embedding_hnsw ON memory_items "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_memory_items_embedding_hnsw", table_name="memory_items")
    op.drop_index("ix_memory_items_type", table_name="memory_items")
    op.drop_table("memory_items")
