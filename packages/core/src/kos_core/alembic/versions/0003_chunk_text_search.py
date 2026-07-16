"""Columna tsvector generada + índice GIN para búsqueda léxica (Sprint 3, doc 08).

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-14

"""

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Columna generada: se mantiene sola al insertar/actualizar chunks.
    # Config 'simple': el vault es multilingüe (es/en); sin stemming agresivo.
    op.execute(
        "ALTER TABLE chunks ADD COLUMN text_search tsvector "
        "GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED"
    )
    op.execute("CREATE INDEX ix_chunks_text_search ON chunks USING gin (text_search)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_text_search")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS text_search")
