"""Columna chunks.entity_node_ids (doc 12 §4): qué nodos de Neo4j salieron de
cada chunk, para que la task de relaciones cross-documento pueda, dado un
chunk_id de OTRO documento sincronizado hace tiempo, saber a qué entidades ya
resueltas corresponde (EntityCandidate.chunk_ids es transitorio, se descarta
al terminar cada graph_sync — esto persiste el mapeo).

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-19

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column(
            "entity_node_ids",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("chunks", "entity_node_ids")
