"""Tabla de fuentes registradas + vínculo desde documents (Sprint 2, doc 06).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-14

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("source_uuid", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("connector", sa.Text, nullable=False),
        sa.Column("config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "source_uuid",
            UUID(as_uuid=True),
            sa.ForeignKey("sources.source_uuid", ondelete="SET NULL"),
        ),
    )
    op.create_index("ix_documents_source_uuid", "documents", ["source_uuid"])


def downgrade() -> None:
    op.drop_index("ix_documents_source_uuid", table_name="documents")
    op.drop_column("documents", "source_uuid")
    op.drop_table("sources")
