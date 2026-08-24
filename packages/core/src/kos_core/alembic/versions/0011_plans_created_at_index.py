"""Índice ix_plans_created_at (necesario para listar/agregar planes por recencia —
GET /v1/plans y GET /v1/plans/metrics, doc 06 §2 addendum 2026-08-21).

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-21

"""

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_index("ix_plans_created_at", "plans", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_plans_created_at", table_name="plans")
