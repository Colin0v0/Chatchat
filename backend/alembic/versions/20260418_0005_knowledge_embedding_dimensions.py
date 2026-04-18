"""Fix knowledge chunk embedding column to a fixed vector dimension.

Revision ID: 20260418_0005
Revises: 20260418_0004
Create Date: 2026-04-18 23:30:00
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import inspect


revision = "20260418_0005"
down_revision = "20260418_0004"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSIONS = 1024


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = inspect(bind)
    if "knowledge_chunks" not in set(inspector.get_table_names()):
        return

    columns = {str(column["name"]) for column in inspector.get_columns("knowledge_chunks")}
    if "embedding" not in columns:
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_ivfflat")
    op.execute(
        f"""
        ALTER TABLE knowledge_chunks
        ALTER COLUMN embedding TYPE vector({EMBEDDING_DIMENSIONS})
        USING embedding::vector
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_ivfflat
        ON knowledge_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = inspect(bind)
    if "knowledge_chunks" not in set(inspector.get_table_names()):
        return

    columns = {str(column["name"]) for column in inspector.get_columns("knowledge_chunks")}
    if "embedding" not in columns:
        return

    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_ivfflat")
    op.execute(
        """
        ALTER TABLE knowledge_chunks
        ALTER COLUMN embedding TYPE vector
        USING embedding::vector
        """
    )
