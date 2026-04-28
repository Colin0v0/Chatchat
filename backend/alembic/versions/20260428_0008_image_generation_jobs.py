"""Add image generation jobs.

Revision ID: 20260428_0008
Revises: 20260427_0007
Create Date: 2026-04-28 12:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260428_0008"
down_revision = "20260427_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "image_generation_jobs" in set(inspector.get_table_names()):
        return

    op.create_table(
        "image_generation_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_message_id", sa.Integer(), nullable=False),
        sa.Column("assistant_message_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("size", sa.String(length=32), nullable=True),
        sa.Column("quality", sa.String(length=32), nullable=True),
        sa.Column("output_format", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_image_generation_jobs_assistant_message_id"), "image_generation_jobs", ["assistant_message_id"])
    op.create_index(op.f("ix_image_generation_jobs_conversation_id"), "image_generation_jobs", ["conversation_id"])
    op.create_index(op.f("ix_image_generation_jobs_id"), "image_generation_jobs", ["id"])
    op.create_index(op.f("ix_image_generation_jobs_status"), "image_generation_jobs", ["status"])
    op.create_index(op.f("ix_image_generation_jobs_user_id"), "image_generation_jobs", ["user_id"])
    op.create_index(op.f("ix_image_generation_jobs_user_message_id"), "image_generation_jobs", ["user_message_id"])
    op.alter_column("image_generation_jobs", "status", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "image_generation_jobs" not in set(inspector.get_table_names()):
        return

    op.drop_index(op.f("ix_image_generation_jobs_user_message_id"), table_name="image_generation_jobs")
    op.drop_index(op.f("ix_image_generation_jobs_user_id"), table_name="image_generation_jobs")
    op.drop_index(op.f("ix_image_generation_jobs_status"), table_name="image_generation_jobs")
    op.drop_index(op.f("ix_image_generation_jobs_id"), table_name="image_generation_jobs")
    op.drop_index(op.f("ix_image_generation_jobs_conversation_id"), table_name="image_generation_jobs")
    op.drop_index(op.f("ix_image_generation_jobs_assistant_message_id"), table_name="image_generation_jobs")
    op.drop_table("image_generation_jobs")
