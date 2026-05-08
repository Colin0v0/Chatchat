"""Persist desktop pet state per user.

Revision ID: 20260508_0012
Revises: 20260430_0011
Create Date: 2026-05-08 16:20:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_0012"
down_revision = "20260430_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 中文注释：每个用户只保留一份桌面宠物状态，方便多设备同步读取同一行。
    op.create_table(
        "pet_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("energy", sa.Integer(), nullable=False),
        sa.Column("hunger", sa.Integer(), nullable=False),
        sa.Column("mood", sa.Integer(), nullable=False),
        sa.Column("thirst", sa.Integer(), nullable=False),
        sa.Column("position_bottom", sa.Float(), nullable=False),
        sa.Column("position_left", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_pet_states_user_id"),
    )
    op.create_index(op.f("ix_pet_states_id"), "pet_states", ["id"], unique=False)
    op.create_index(op.f("ix_pet_states_user_id"), "pet_states", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pet_states_user_id"), table_name="pet_states")
    op.drop_index(op.f("ix_pet_states_id"), table_name="pet_states")
    op.drop_table("pet_states")
