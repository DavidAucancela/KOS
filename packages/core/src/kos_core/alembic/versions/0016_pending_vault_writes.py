"""Tabla pending_vault_writes: escrituras al vault diferidas (doc 14 §5).

En el despliegue gestionado la API no tiene el filesystem del vault (vive en el
volumen del servicio cron, y un volumen se adjunta a un solo servicio). Las
herramientas de escritura encolan aquí la intención y el drain la materializa.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-12

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "pending_vault_writes",
        sa.Column("write_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("op", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_path", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_pending_vault_writes_status",
        "pending_vault_writes",
        ["status", "requested_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_pending_vault_writes_status", table_name="pending_vault_writes")
    op.drop_table("pending_vault_writes")
