"""plans.post (Sprint 21, doc 03 §3): registro declarativo de post-pasos.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-16

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("post", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("plans", "post")
