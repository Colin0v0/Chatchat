"""Add MemoryOS-style mid-term memory segments.

Revision ID: 20260611_0017
Revises: 20260529_0016
Create Date: 2026-06-11 12:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from pgvector.sqlalchemy import Vector


revision = "20260611_0017"
down_revision = "20260529_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    if "memory_segments" not in tables:
        op.create_table(
            "memory_segments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("keywords_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("embedding", Vector(1024), nullable=True),
            sa.Column("visit_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("interaction_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("heat", sa.Float(), nullable=False, server_default="0"),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_analyzed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_memory_segments_id", "memory_segments", ["id"])
        op.create_index("ix_memory_segments_user_id", "memory_segments", ["user_id"])
        op.create_index("ix_memory_segments_user_heat", "memory_segments", ["user_id", "heat"])

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "memory_pages" not in tables:
        op.create_table(
            "memory_pages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("segment_id", sa.Integer(), nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("user_message_id", sa.Integer(), nullable=False),
            sa.Column("assistant_message_id", sa.Integer(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("excerpt", sa.Text(), nullable=False, server_default=""),
            sa.Column("keywords_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("embedding", Vector(1024), nullable=True),
            sa.Column("analyzed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["assistant_message_id"], ["messages.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["segment_id"], ["memory_segments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_message_id"], ["messages.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("assistant_message_id", name="uq_memory_pages_assistant_message_id"),
        )
        op.create_index("ix_memory_pages_id", "memory_pages", ["id"])
        op.create_index("ix_memory_pages_user_id", "memory_pages", ["user_id"])
        op.create_index("ix_memory_pages_segment_id", "memory_pages", ["segment_id"])
        op.create_index("ix_memory_pages_conversation_id", "memory_pages", ["conversation_id"])

    if bind.dialect.name == "postgresql":
        # 中文注释：向量索引用于中期记忆相似度召回，文本索引用于关键词召回。
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_memory_segments_embedding_ivfflat
            ON memory_segments
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_memory_pages_embedding_ivfflat
            ON memory_pages
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_memory_segments_search_text_trgm
            ON memory_segments
            USING gin (
                lower(
                    coalesce(title, '')
                    || ' '
                    || coalesce(summary, '')
                    || ' '
                    || coalesce(keywords_json, '')
                ) gin_trgm_ops
            )
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_memory_pages_search_text_trgm
            ON memory_pages
            USING gin (
                lower(
                    coalesce(summary, '')
                    || ' '
                    || coalesce(excerpt, '')
                    || ' '
                    || coalesce(keywords_json, '')
                ) gin_trgm_ops
            )
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_memory_pages_search_text_trgm")
        op.execute("DROP INDEX IF EXISTS ix_memory_segments_search_text_trgm")
        op.execute("DROP INDEX IF EXISTS ix_memory_pages_embedding_ivfflat")
        op.execute("DROP INDEX IF EXISTS ix_memory_segments_embedding_ivfflat")

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "memory_pages" in tables:
        op.drop_index("ix_memory_pages_conversation_id", table_name="memory_pages")
        op.drop_index("ix_memory_pages_segment_id", table_name="memory_pages")
        op.drop_index("ix_memory_pages_user_id", table_name="memory_pages")
        op.drop_index("ix_memory_pages_id", table_name="memory_pages")
        op.drop_table("memory_pages")

    if "memory_segments" in tables:
        op.drop_index("ix_memory_segments_user_heat", table_name="memory_segments")
        op.drop_index("ix_memory_segments_user_id", table_name="memory_segments")
        op.drop_index("ix_memory_segments_id", table_name="memory_segments")
        op.drop_table("memory_segments")
