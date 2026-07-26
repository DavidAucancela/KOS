"""doc_type de documentos: "content" | "template" (Sprint 8, doc 02 §2).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-24

"""

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("doc_type", sa.Text(), nullable=False, server_default="content"),
    )
    op.create_index("ix_documents_doc_type", "documents", ["doc_type"])


def downgrade() -> None:
    op.drop_index("ix_documents_doc_type", table_name="documents")
    op.drop_column("documents", "doc_type")
