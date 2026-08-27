"""Tablas conversations + messages (historial de chat persistente, doc 06 §2 addendum
2026-08-21, "Monitoreo" en docs/deuda-tecnica.md).

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-21

Renumerada de 0010 a 0012 (2026-08-27): esta línea (historial de chat / métricas,
rama `historial-chat-y-metricas-planner`) y la de calidad de grafo
(`0010_node_embeddings`, `0011_chunk_entity_node_ids`) ramificaron de 0009 en
paralelo reusando los mismos IDs, dejando `alembic upgrade head` roto con
"Multiple head revisions". Se reencadena lineal detrás de 0011.
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
        "conversations",
        sa.Column("conversation_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_conversations_updated_at", "conversations", ["updated_at"])

    op.create_table(
        "messages",
        sa.Column("message_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        # Sin FK a plans: las ramas sintéticas (/crear-nota, /nueva-maquina, intención de
        # plantilla) generan un plan_id sin fila real en `plans` (ver doc 06 §2 addendum).
        sa.Column("plan_id", UUID(as_uuid=True)),
        sa.Column("evidence", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("confidence", sa.Float),
        sa.Column("degraded", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_messages_conversation_id_created_at",
        "messages",
        ["conversation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_id_created_at", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_updated_at", table_name="conversations")
    op.drop_table("conversations")
