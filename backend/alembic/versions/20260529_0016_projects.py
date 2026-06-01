"""Add project spaces.

Revision ID: 20260529_0016
Revises: 20260512_0015
Create Date: 2026-05-29 12:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260529_0016"
down_revision = "20260512_0015"
branch_labels = None
depends_on = None


def _table_columns(inspector, table_name: str) -> set[str]:
    return {str(column["name"]) for column in inspector.get_columns(table_name)}


def _table_indexes(inspector, table_name: str) -> set[str]:
    return {str(index["name"]) for index in inspector.get_indexes(table_name)}


def _table_unique_constraints(inspector, table_name: str) -> set[str]:
    return {
        str(constraint["name"])
        for constraint in inspector.get_unique_constraints(table_name)
        if constraint.get("name")
    }


def _add_project_column(inspector, table_name: str) -> None:
    if "project_id" in _table_columns(inspector, table_name):
        return
    op.add_column(
        table_name,
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(f"ix_{table_name}_project_id", table_name, ["project_id"], unique=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "projects" not in tables:
        op.create_table(
            "projects",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("default_model", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "name", name="uq_projects_user_name"),
        )
        op.create_index("ix_projects_id", "projects", ["id"], unique=False)
        op.create_index("ix_projects_user_id", "projects", ["user_id"], unique=False)

    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    for table_name in ("conversations", "knowledge_documents", "knowledge_chunks"):
        if table_name in tables:
            _add_project_column(inspector, table_name)

    if "knowledge_folders" in tables:
        _add_project_column(inspector, "knowledge_folders")
        unique_constraints = _table_unique_constraints(inspector, "knowledge_folders")
        if "uq_knowledge_folders_user_name" in unique_constraints:
            op.drop_constraint("uq_knowledge_folders_user_name", "knowledge_folders", type_="unique")
        if "uq_knowledge_folders_user_project_name" not in unique_constraints:
            op.create_unique_constraint(
                "uq_knowledge_folders_user_project_name",
                "knowledge_folders",
                ["user_id", "project_id", "name"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "knowledge_folders" in tables:
        unique_constraints = _table_unique_constraints(inspector, "knowledge_folders")
        if "uq_knowledge_folders_user_project_name" in unique_constraints:
            op.drop_constraint("uq_knowledge_folders_user_project_name", "knowledge_folders", type_="unique")
        if "uq_knowledge_folders_user_name" not in unique_constraints:
            op.create_unique_constraint(
                "uq_knowledge_folders_user_name",
                "knowledge_folders",
                ["user_id", "name"],
            )

    for table_name in ("knowledge_chunks", "knowledge_folders", "knowledge_documents", "conversations"):
        if table_name not in tables:
            continue
        columns = _table_columns(inspector, table_name)
        indexes = _table_indexes(inspector, table_name)
        index_name = f"ix_{table_name}_project_id"
        if index_name in indexes:
            op.drop_index(index_name, table_name=table_name)
        if "project_id" in columns:
            op.drop_column(table_name, "project_id")

    if "projects" in tables:
        op.drop_index("ix_projects_user_id", table_name="projects")
        op.drop_index("ix_projects_id", table_name="projects")
        op.drop_table("projects")
