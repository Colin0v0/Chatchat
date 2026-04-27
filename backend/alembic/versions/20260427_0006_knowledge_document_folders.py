"""Add logical folders for knowledge documents.

Revision ID: 20260427_0006
Revises: 20260418_0005
Create Date: 2026-04-27 20:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260427_0006"
down_revision = "20260418_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "knowledge_documents" not in set(inspector.get_table_names()):
        return

    columns = {str(column["name"]) for column in inspector.get_columns("knowledge_documents")}
    if "folder" not in columns:
        op.add_column(
            "knowledge_documents",
            sa.Column("folder", sa.String(length=255), nullable=False, server_default=""),
        )
        op.alter_column("knowledge_documents", "folder", server_default=None)

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_knowledge_documents_user_folder
            ON knowledge_documents (user_id, folder)
            """
        )
    else:
        try:
            op.create_index(
                "ix_knowledge_documents_user_folder",
                "knowledge_documents",
                ["user_id", "folder"],
            )
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "knowledge_documents" not in set(inspector.get_table_names()):
        return

    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_knowledge_documents_user_folder")
    else:
        try:
            op.drop_index("ix_knowledge_documents_user_folder", table_name="knowledge_documents")
        except Exception:
            pass

    columns = {str(column["name"]) for column in inspector.get_columns("knowledge_documents")}
    if "folder" in columns:
        op.drop_column("knowledge_documents", "folder")
