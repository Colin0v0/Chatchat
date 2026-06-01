from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..projects import get_user_project
from ..providers import normalize_model, resolve_model_profile
from ..schemas import ProjectCreate, ProjectOut, ProjectUpdate
from ..storage.database import get_db
from ..storage.models import Conversation, KnowledgeChunk, KnowledgeDocument, KnowledgeFolder, Project, User

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _normalize_project_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Project name is required")
    return normalized


def _normalize_project_default_model(model: str | None) -> str | None:
    raw_model = (model or "").strip()
    if not raw_model:
        return None
    normalized = normalize_model(raw_model)
    if resolve_model_profile(normalized) is None:
        raise HTTPException(status_code=400, detail=f"Model not enabled: {normalized}")
    return normalized


def _ensure_project_name_available(
    db: Session,
    *,
    user_id: int,
    name: str,
    exclude_project_id: int | None = None,
) -> None:
    query = select(Project.id).where(Project.user_id == user_id, Project.name == name)
    if exclude_project_id is not None:
        query = query.where(Project.id != exclude_project_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=400, detail="Project name already exists")


def _commit_project_change(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Project name already exists") from exc


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    return list(
        db.scalars(
            select(Project)
            .where(Project.user_id == current_user.id)
            .order_by(Project.updated_at.desc(), Project.id.desc())
        ).all()
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    name = _normalize_project_name(payload.name)
    _ensure_project_name_available(db, user_id=current_user.id, name=name)
    project = Project(
        user_id=current_user.id,
        name=name,
        description=payload.description.strip(),
        default_model=_normalize_project_default_model(payload.default_model),
    )
    db.add(project)
    _commit_project_change(db)
    db.refresh(project)
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    project = get_user_project(db, user_id=current_user.id, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if "name" in payload.model_fields_set and payload.name is not None:
        name = _normalize_project_name(payload.name)
        _ensure_project_name_available(
            db,
            user_id=current_user.id,
            name=name,
            exclude_project_id=project.id,
        )
        project.name = name
    if "description" in payload.model_fields_set and payload.description is not None:
        project.description = payload.description.strip()
    if "default_model" in payload.model_fields_set:
        project.default_model = _normalize_project_default_model(payload.default_model)
    project.updated_at = datetime.now(timezone.utc)

    db.add(project)
    _commit_project_change(db)
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    project = get_user_project(db, user_id=current_user.id, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    # 中文注释：删除项目只移除空间壳子，聊天和知识库文档改回未归档，避免误删用户内容。
    for model in (Conversation, KnowledgeDocument, KnowledgeFolder, KnowledgeChunk):
        db.execute(
            update(model)
            .where(model.user_id == current_user.id, model.project_id == project.id)
            .values(project_id=None)
        )
    db.delete(project)
    db.commit()
