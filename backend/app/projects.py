from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .storage.models import Project


def get_user_project(
    db: Session,
    *,
    user_id: int,
    project_id: int,
) -> Project | None:
    return db.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
    )


def require_user_project(
    db: Session,
    *,
    user_id: int,
    project_id: int | None,
) -> Project | None:
    if project_id is None:
        return None
    project = get_user_project(db, user_id=user_id, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
