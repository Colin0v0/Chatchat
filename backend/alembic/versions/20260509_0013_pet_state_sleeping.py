"""Persist desktop pet sleeping state.

Revision ID: 20260509_0013
Revises: 20260508_0012
Create Date: 2026-05-09 11:20:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260509_0013"
down_revision = "20260508_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 中文注释：睡眠状态必须单独持久化，不能再靠精力值反推，否则自动睡着后会被重新判醒。
    op.add_column(
        "pet_states",
        sa.Column("sleeping", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("pet_states", "sleeping")
