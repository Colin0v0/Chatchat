"""Add memory settings and chat history recall index.

Revision ID: 20260512_0015
Revises: 20260512_0014
Create Date: 2026-05-12 20:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from pgvector.sqlalchemy import Vector


revision = "20260512_0015"
down_revision = "20260512_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "conversations" in tables:
        conversation_columns = {str(column["name"]) for column in inspector.get_columns("conversations")}
        if "temporary_chat" not in conversation_columns:
            op.add_column(
                "conversations",
                sa.Column("temporary_chat", sa.Boolean(), nullable=False, server_default=sa.false()),
            )

    if "user_memory_settings" not in tables:
        op.create_table(
            "user_memory_settings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("saved_memories_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("reference_chat_history_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("memory_learning_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("sensitive_memory_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", name="uq_user_memory_settings_user_id"),
        )
        op.create_index("ix_user_memory_settings_id", "user_memory_settings", ["id"])
        op.create_index("ix_user_memory_settings_user_id", "user_memory_settings", ["user_id"])

    if "chat_history_entries" not in tables:
        op.create_table(
            "chat_history_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("user_message_id", sa.Integer(), nullable=False),
            sa.Column("assistant_message_id", sa.Integer(), nullable=False),
            sa.Column("conversation_title", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("user_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("assistant_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("embedding", Vector(1024), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["assistant_message_id"], ["messages.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_message_id"], ["messages.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("assistant_message_id", name="uq_chat_history_entries_assistant_message_id"),
        )
        op.create_index("ix_chat_history_entries_id", "chat_history_entries", ["id"])
        op.create_index("ix_chat_history_entries_user_id", "chat_history_entries", ["user_id"])
        op.create_index("ix_chat_history_entries_conversation_id", "chat_history_entries", ["conversation_id"])
        op.create_index(
            "ix_chat_history_entries_user_updated_at",
            "chat_history_entries",
            ["user_id", "updated_at"],
        )

    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_chat_history_entries_embedding_ivfflat
            ON chat_history_entries
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_chat_history_entries_search_text_trgm
            ON chat_history_entries
            USING gin (
                lower(
                    coalesce(conversation_title, '')
                    || ' '
                    || coalesce(user_text, '')
                    || ' '
                    || coalesce(assistant_text, '')
                    || ' '
                    || coalesce(summary, '')
                ) gin_trgm_ops
            )
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_chat_history_entries_search_text_trgm")
        op.execute("DROP INDEX IF EXISTS ix_chat_history_entries_embedding_ivfflat")

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "chat_history_entries" in tables:
        op.drop_index("ix_chat_history_entries_user_updated_at", table_name="chat_history_entries")
        op.drop_index("ix_chat_history_entries_conversation_id", table_name="chat_history_entries")
        op.drop_index("ix_chat_history_entries_user_id", table_name="chat_history_entries")
        op.drop_index("ix_chat_history_entries_id", table_name="chat_history_entries")
        op.drop_table("chat_history_entries")
    if "user_memory_settings" in tables:
        op.drop_index("ix_user_memory_settings_user_id", table_name="user_memory_settings")
        op.drop_index("ix_user_memory_settings_id", table_name="user_memory_settings")
        op.drop_table("user_memory_settings")
    if "conversations" in tables:
        conversation_columns = {str(column["name"]) for column in inspector.get_columns("conversations")}
        if "temporary_chat" in conversation_columns:
            op.drop_column("conversations", "temporary_chat")
