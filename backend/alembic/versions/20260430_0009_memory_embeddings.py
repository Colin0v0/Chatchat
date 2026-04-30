"""Add embedding column to memory_items for vector recall.

Revision ID: 20260430_0009
Revises: 20260428_0008
Create Date: 2026-04-30 12:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from pgvector.sqlalchemy import Vector


revision = "20260430_0009"
down_revision = "20260428_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "memory_items" not in set(inspector.get_table_names()):
        return

    columns = {str(column["name"]) for column in inspector.get_columns("memory_items")}
    if "embedding" in columns:
        return

    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.add_column("memory_items", sa.Column("embedding", Vector(1024), nullable=True))
        return

    # Fallback for non-postgres (should not happen in practice)
    with op.batch_alter_table("memory_items") as batch_op:
        batch_op.add_column(sa.Column("embedding", Vector(1024), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "memory_items" not in set(inspector.get_table_names()):
        return

    columns = {str(column["name"]) for column in inspector.get_columns("memory_items")}
    if "embedding" not in columns:
        return

    if bind.dialect.name == "postgresql":
        op.drop_column("memory_items", "embedding")
        return

    with op.batch_alter_table("memory_items") as batch_op:
        batch_op.drop_column("embedding")
