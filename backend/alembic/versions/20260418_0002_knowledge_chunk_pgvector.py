"""Move knowledge chunk embeddings to pgvector-backed column.

Revision ID: 20260418_0002
Revises: 20260417_0001
Create Date: 2026-04-18 03:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "20260418_0002"
down_revision = "20260417_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.add_column("knowledge_chunks", sa.Column("embedding", Vector(), nullable=True))
        op.execute('UPDATE knowledge_chunks SET embedding = embedding_json::vector WHERE embedding_json IS NOT NULL')
        op.alter_column("knowledge_chunks", "embedding", nullable=False)
        op.drop_column("knowledge_chunks", "embedding_json")
        return

    with op.batch_alter_table("knowledge_chunks") as batch_op:
        batch_op.add_column(sa.Column("embedding", Vector(), nullable=True))
        batch_op.drop_column("embedding_json")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.add_column("knowledge_chunks", sa.Column("embedding_json", sa.Text(), nullable=True))
        op.execute('UPDATE knowledge_chunks SET embedding_json = embedding::text WHERE embedding IS NOT NULL')
        op.alter_column("knowledge_chunks", "embedding_json", nullable=False)
        op.drop_column("knowledge_chunks", "embedding")
        return

    with op.batch_alter_table("knowledge_chunks") as batch_op:
        batch_op.add_column(sa.Column("embedding_json", sa.Text(), nullable=True))
        batch_op.drop_column("embedding")
