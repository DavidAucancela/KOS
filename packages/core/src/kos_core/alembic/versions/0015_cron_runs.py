"""Tabla cron_runs: ejecuciones del drain programado (doc 14 §4, ADR-0009).

En el despliegue gestionado el worker no es un proceso vivo sino un cron job de
Railway que arranca, drena la cola y sale. Su modo de fallo característico es
silencioso: si una ejecución no termina, Railway salta las siguientes y la
ingesta se detiene sin error visible. Esta tabla es lo que `/v1/ops/status`
consulta para que eso se note.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-12

"""

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "cron_runs",
        sa.Column("run_id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job", sa.Text(), nullable=False, server_default=sa.text("'drain'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'running'")),
        sa.Column("tasks_drained", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("detail", sa.Text(), nullable=True),
    )
    op.create_index("ix_cron_runs_started_at", "cron_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_cron_runs_started_at", table_name="cron_runs")
    op.drop_table("cron_runs")
