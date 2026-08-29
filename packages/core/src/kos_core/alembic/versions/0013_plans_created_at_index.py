"""Índice ix_plans_created_at (necesario para listar/agregar planes por recencia —
GET /v1/plans y GET /v1/plans/metrics, doc 06 §2 addendum 2026-08-21).

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-21

Renumerada de 0011 a 0013 (2026-08-27): ver la nota en 0012_conversations.py.
"""

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_index("ix_plans_created_at", "plans", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_plans_created_at", table_name="plans")
