"""Drop legacy message attachment upstream_file_id column.

Revision ID: 20260418_0003
Revises: 20260418_0002
Create Date: 2026-04-18 18:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260418_0003"
down_revision = "20260418_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "message_attachments" not in set(inspector.get_table_names()):
        return

    columns = {str(column["name"]) for column in inspector.get_columns("message_attachments")}
    if "upstream_file_id" not in columns:
        return

    if bind.dialect.name == "postgresql":
        op.drop_column("message_attachments", "upstream_file_id")
        return

    with op.batch_alter_table("message_attachments") as batch_op:
        batch_op.drop_column("upstream_file_id")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "message_attachments" not in set(inspector.get_table_names()):
        return

    columns = {str(column["name"]) for column in inspector.get_columns("message_attachments")}
    if "upstream_file_id" in columns:
        return

    if bind.dialect.name == "postgresql":
        op.add_column("message_attachments", sa.Column("upstream_file_id", sa.String(length=255), nullable=True))
        return

    with op.batch_alter_table("message_attachments") as batch_op:
        batch_op.add_column(sa.Column("upstream_file_id", sa.String(length=255), nullable=True))
