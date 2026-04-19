"""Add PostgreSQL-first indexes for knowledge chunk retrieval.

Revision ID: 20260418_0004
Revises: 20260418_0003
Create Date: 2026-04-18 15:00:00
"""
from __future__ import annotations

from alembic import op
from sqlalchemy.exc import DBAPIError


revision = "20260418_0004"
down_revision = "20260418_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_user_path_chunk_index
        ON knowledge_chunks (user_id, path, chunk_index)
        """
    )
    try:
        with bind.begin_nested():
            op.execute(
                """
                CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_ivfflat
                ON knowledge_chunks
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
                """
            )
    except DBAPIError as exc:
        message = str(getattr(exc, "orig", exc)).lower()
        if "does not have dimensions" not in message:
            raise
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_search_text_trgm
        ON knowledge_chunks
        USING gin (
            lower(
                coalesce(path, '')
                || ' '
                || coalesce(directory, '')
                || ' '
                || coalesce(heading, '')
                || ' '
                || coalesce(tags_json, '')
                || ' '
                || coalesce(content, '')
            ) gin_trgm_ops
        )
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_search_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_ivfflat")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_user_path_chunk_index")
