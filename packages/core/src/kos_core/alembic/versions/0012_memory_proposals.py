"""Tabla memory_proposals (mitigación del riesgo documentado en
docs/deuda-tecnica.md: `memory.store` elegido por el Planner nunca se
auto-aprueba — un intento sin `confirm=true` queda acá para revisión humana).

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-26

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "memory_proposals",
        sa.Column("proposal_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("sources", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("confidence", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("rejected_reason", sa.Text),
        sa.Column("memory_id", UUID(as_uuid=True)),
        sa.Column("trace_id", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_memory_proposals_status", "memory_proposals", ["status"])
    op.create_index("ix_memory_proposals_created_at", "memory_proposals", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_memory_proposals_created_at", table_name="memory_proposals")
    op.drop_index("ix_memory_proposals_status", table_name="memory_proposals")
    op.drop_table("memory_proposals")
