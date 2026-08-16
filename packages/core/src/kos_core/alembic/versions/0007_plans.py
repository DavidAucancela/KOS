"""Tabla plans (Sprint 19, doc 03 §3 regla 3, doc 06 línea 59, v0.5 Fase 4).

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-16

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("plan_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("steps", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("degraded", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("degraded_reason", sa.Text),
        sa.Column("elapsed_ms", sa.Float, nullable=False, server_default=sa.text("0")),
        sa.Column("trace_id", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_plans_trace_id", "plans", ["trace_id"])


def downgrade() -> None:
    op.drop_index("ix_plans_trace_id", table_name="plans")
    op.drop_table("plans")
