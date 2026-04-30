"""Add persistent battle sessions.

Revision ID: 20260430_0010
Revises: 20260430_0009
Create Date: 2026-04-30 16:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260430_0010"
down_revision = "20260430_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "battle_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("rounds_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_battle_sessions_user_id", "battle_sessions", ["user_id"])
    op.create_index("ix_battle_sessions_updated_at", "battle_sessions", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_battle_sessions_updated_at", table_name="battle_sessions")
    op.drop_index("ix_battle_sessions_user_id", table_name="battle_sessions")
    op.drop_table("battle_sessions")
