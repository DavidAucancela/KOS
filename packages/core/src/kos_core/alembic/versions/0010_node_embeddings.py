"""Tabla node_embeddings (doc 12 §3): embeddings de nodo persistidos para
resolución de entidades indexada, reemplazando el loop de coseno en memoria
de graph_sync.py::_resolve_entity.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-19

"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | None = None
depends_on: str | None = None

EMBEDDING_DIM = 1024  # bge-m3


def upgrade() -> None:
    op.create_table(
        "node_embeddings",
        sa.Column("node_id", sa.Text(), primary_key=True),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("node_type", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_node_embeddings_type", "node_embeddings", ["node_type"])
    op.execute(
        "CREATE INDEX ix_node_embeddings_embedding_hnsw ON node_embeddings "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_node_embeddings_embedding_hnsw", table_name="node_embeddings")
    op.drop_index("ix_node_embeddings_type", table_name="node_embeddings")
    op.drop_table("node_embeddings")
