"""Create PostgreSQL baseline schema for current Chatchat models.

Revision ID: 20260416_0000
Revises:
Create Date: 2026-04-16 23:00:00
"""
from __future__ import annotations

from alembic import op

from app.storage.database import Base
from app.storage import models as storage_models  # noqa: F401


revision = "20260416_0000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, checkfirst=True)
