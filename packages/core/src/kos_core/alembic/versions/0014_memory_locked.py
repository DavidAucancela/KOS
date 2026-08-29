"""Columna memory_items.locked: corrección manual de memoria (doc 04 §5,
análogo a `locked` en nodos/relaciones del grafo, Sprint 9, doc 02 §4 regla 5).

Una memoria `locked` la fijó el usuario: no se recalcula su `confidence` al
perder una fuente ni se archiva al quedarse sin ninguna, y queda fuera de la
consolidación episódica→semántica.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-27

"""

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "memory_items",
        sa.Column(
            "locked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )


def downgrade() -> None:
    op.drop_column("memory_items", "locked")
