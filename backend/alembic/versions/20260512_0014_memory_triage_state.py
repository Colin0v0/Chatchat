"""Add memory triage state and evidence tracking.

Revision ID: 20260512_0014
Revises: 20260509_0013
Create Date: 2026-05-12 18:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260512_0014"
down_revision = "20260509_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "memory_items" not in set(inspector.get_table_names()):
        return

    columns = {str(column["name"]) for column in inspector.get_columns("memory_items")}
    # 中文注释：置信状态和证据计数用于分诊记忆，不再只靠 active/status 判断是否可信。
    if "confidence_state" not in columns:
        op.add_column(
            "memory_items",
            sa.Column("confidence_state", sa.String(length=24), nullable=False, server_default="inferred"),
        )
    if "evidence_count" not in columns:
        op.add_column(
            "memory_items",
            sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="1"),
        )
    if "evidence_json" not in columns:
        op.add_column(
            "memory_items",
            sa.Column("evidence_json", sa.Text(), nullable=False, server_default="[]"),
        )

    memory_items = sa.table(
        "memory_items",
        sa.column("source_type", sa.String(length=24)),
        sa.column("write_policy", sa.String(length=24)),
        sa.column("status", sa.String(length=24)),
        sa.column("confidence_state", sa.String(length=24)),
        sa.column("evidence_count", sa.Integer()),
        sa.column("evidence_json", sa.Text()),
    )
    op.execute(
        memory_items.update()
        .where(memory_items.c.source_type == "manual")
        .values(confidence_state="confirmed")
    )
    op.execute(
        memory_items.update()
        .where(memory_items.c.write_policy == "explicit")
        .values(confidence_state="confirmed")
    )
    op.execute(
        memory_items.update()
        .where(memory_items.c.status == "archived")
        .values(confidence_state="rejected")
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "memory_items" not in set(inspector.get_table_names()):
        return

    columns = {str(column["name"]) for column in inspector.get_columns("memory_items")}
    if "evidence_json" in columns:
        op.drop_column("memory_items", "evidence_json")
    if "evidence_count" in columns:
        op.drop_column("memory_items", "evidence_count")
    if "confidence_state" in columns:
        op.drop_column("memory_items", "confidence_state")
