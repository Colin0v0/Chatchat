"""Remove candidate memory state and promote legacy auto memories.

Revision ID: 20260430_0011
Revises: 20260430_0010
Create Date: 2026-04-30 21:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260430_0011"
down_revision = "20260430_0010"
branch_labels = None
depends_on = None


memory_items = sa.table(
    "memory_items",
    sa.column("status", sa.String(length=24)),
    sa.column("active", sa.Boolean()),
    sa.column("scope", sa.String(length=24)),
    sa.column("source_type", sa.String(length=24)),
    sa.column("write_policy", sa.String(length=24)),
    sa.column("last_confirmed_at", sa.DateTime(timezone=True)),
    sa.column("promoted_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    candidate_status_filter = memory_items.c.status == "candidate"
    auto_candidate_policy_filter = memory_items.c.write_policy == "auto_candidate"

    # 中文注释：旧版 candidate 代表“待确认的长期信息”，新策略里这类信息应直接成为全局 active 记忆。
    op.execute(
        memory_items.update()
        .where(sa.or_(candidate_status_filter, auto_candidate_policy_filter))
        .values(
            status=sa.case((candidate_status_filter, "active"), else_=memory_items.c.status),
            active=sa.case((candidate_status_filter, sa.true()), else_=memory_items.c.active),
            scope=sa.case(
                (
                    sa.and_(candidate_status_filter, memory_items.c.scope == "conversation"),
                    "global",
                ),
                else_=memory_items.c.scope,
            ),
            write_policy=sa.case(
                (auto_candidate_policy_filter, "explicit"),
                else_=memory_items.c.write_policy,
            ),
            last_confirmed_at=sa.case(
                (
                    sa.and_(candidate_status_filter, memory_items.c.last_confirmed_at.is_(None)),
                    sa.func.now(),
                ),
                else_=memory_items.c.last_confirmed_at,
            ),
            updated_at=sa.func.now(),
        )
    )


def downgrade() -> None:
    legacy_auto_global_filter = sa.and_(
        memory_items.c.source_type == "auto",
        memory_items.c.scope == "global",
        memory_items.c.status == "active",
        memory_items.c.write_policy == "explicit",
        memory_items.c.promoted_at.is_(None),
    )

    # 中文注释：回滚时按旧语义恢复自动长期记忆的“待确认”状态。
    op.execute(
        memory_items.update()
        .where(legacy_auto_global_filter)
        .values(
            status="candidate",
            active=sa.false(),
            scope="conversation",
            write_policy="auto_candidate",
            last_confirmed_at=None,
            updated_at=sa.func.now(),
        )
    )
