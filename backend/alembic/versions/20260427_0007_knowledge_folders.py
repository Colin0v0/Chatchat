"""Add persisted knowledge folders.

Revision ID: 20260427_0007
Revises: 20260427_0006
Create Date: 2026-04-27 21:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260427_0007"
down_revision = "20260427_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "knowledge_folders" not in existing_tables:
        op.create_table(
            "knowledge_folders",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "name", name="uq_knowledge_folders_user_name"),
        )
        op.create_index(op.f("ix_knowledge_folders_id"), "knowledge_folders", ["id"], unique=False)
        op.create_index(op.f("ix_knowledge_folders_user_id"), "knowledge_folders", ["user_id"], unique=False)

    existing_tables = set(inspector.get_table_names())
    if "knowledge_documents" not in existing_tables or "knowledge_folders" not in existing_tables:
        return

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            INSERT INTO knowledge_folders (user_id, name)
            SELECT DISTINCT user_id, folder
            FROM knowledge_documents
            WHERE folder IS NOT NULL AND folder <> ''
            ON CONFLICT (user_id, name) DO NOTHING
            """
        )
    else:
        op.execute(
            """
            INSERT OR IGNORE INTO knowledge_folders (user_id, name)
            SELECT DISTINCT user_id, folder
            FROM knowledge_documents
            WHERE folder IS NOT NULL AND folder <> ''
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "knowledge_folders" not in set(inspector.get_table_names()):
        return
    op.drop_index(op.f("ix_knowledge_folders_user_id"), table_name="knowledge_folders")
    op.drop_index(op.f("ix_knowledge_folders_id"), table_name="knowledge_folders")
    op.drop_table("knowledge_folders")
