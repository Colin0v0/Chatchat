"""Add runtime tracing foundation tables.

Revision ID: 20260417_0001
Revises:
Create Date: 2026-04-17 23:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260417_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("request_message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("response_message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default="chat"),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("provider_family", sa.String(length=48), nullable=False),
        sa.Column("reasoning_profile", sa.String(length=32), nullable=False, server_default="auto"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="running"),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_runs_conversation_id", "runs", ["conversation_id"])
    op.create_index("ix_runs_user_id", "runs", ["user_id"])
    op.create_index("ix_runs_request_message_id", "runs", ["request_message_id"])
    op.create_index("ix_runs_response_message_id", "runs", ["response_message_id"])
    op.create_index("ix_runs_mode", "runs", ["mode"])
    op.create_index("ix_runs_model_id", "runs", ["model_id"])
    op.create_index("ix_runs_provider_family", "runs", ["provider_family"])
    op.create_index("ix_runs_status", "runs", ["status"])

    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("run_id", "sequence_no", name="uq_run_events_run_id_sequence_no"),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])
    op.create_index("ix_run_events_event_type", "run_events", ["event_type"])

    op.create_table(
        "provider_file_refs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("attachment_id", sa.Integer(), sa.ForeignKey("message_attachments.id"), nullable=False),
        sa.Column("provider_family", sa.String(length=48), nullable=False),
        sa.Column("base_url_hash", sa.String(length=64), nullable=False),
        sa.Column("remote_file_id", sa.String(length=255), nullable=False),
        sa.Column("remote_purpose", sa.String(length=64), nullable=False, server_default="user_data"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "attachment_id",
            "provider_family",
            "base_url_hash",
            name="uq_provider_file_refs_attachment_provider_base",
        ),
    )
    op.create_index("ix_provider_file_refs_attachment_id", "provider_file_refs", ["attachment_id"])
    op.create_index("ix_provider_file_refs_provider_family", "provider_file_refs", ["provider_family"])


def downgrade() -> None:
    op.drop_index("ix_provider_file_refs_provider_family", table_name="provider_file_refs")
    op.drop_index("ix_provider_file_refs_attachment_id", table_name="provider_file_refs")
    op.drop_table("provider_file_refs")

    op.drop_index("ix_run_events_event_type", table_name="run_events")
    op.drop_index("ix_run_events_run_id", table_name="run_events")
    op.drop_table("run_events")

    op.drop_index("ix_runs_status", table_name="runs")
    op.drop_index("ix_runs_provider_family", table_name="runs")
    op.drop_index("ix_runs_model_id", table_name="runs")
    op.drop_index("ix_runs_mode", table_name="runs")
    op.drop_index("ix_runs_response_message_id", table_name="runs")
    op.drop_index("ix_runs_request_message_id", table_name="runs")
    op.drop_index("ix_runs_user_id", table_name="runs")
    op.drop_index("ix_runs_conversation_id", table_name="runs")
    op.drop_table("runs")
