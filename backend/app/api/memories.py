from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..chat.state import get_chat_services
from ..schemas import (
    MemoryCollectionOut,
    MemoryCreate,
    MemoryItemOut,
    MemoryLayerCollectionOut,
    MemoryPromote,
    MemoryUpdate,
)
from ..storage.access import get_user_conversation
from ..storage.database import get_db
from ..storage.models import MemoryItem, User

router = APIRouter(prefix="/api/memories", tags=["memories"])


def _list_memories_response(
    *,
    request: Request,
    conversation_id: Optional[int],
    db: Session,
    current_user: User,
) -> MemoryCollectionOut:
    services = get_chat_services(request)
    if conversation_id is not None and get_user_conversation(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    ) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    workspace = services.memory_service.list_workspace(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    return MemoryCollectionOut(
        documents=list(workspace.documents),
        active_items=MemoryLayerCollectionOut(
            global_items=list(workspace.active_global_items),
            conversation_items=list(workspace.active_conversation_items),
            working_items=list(workspace.active_working_items),
        ),
        candidate_items=MemoryLayerCollectionOut(
            global_items=list(workspace.candidate_global_items),
            conversation_items=list(workspace.candidate_conversation_items),
            working_items=[],
        ),
    )


def _create_memory_response(
    *,
    payload: MemoryCreate,
    request: Request,
    db: Session,
    current_user: User,
) -> MemoryItemOut:
    services = get_chat_services(request)
    if payload.scope == "conversation":
        if payload.conversation_id is None:
            raise HTTPException(status_code=400, detail="Conversation memory requires conversation_id")
        if get_user_conversation(
            db,
            conversation_id=payload.conversation_id,
            user_id=current_user.id,
        ) is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

    return services.memory_service.create_manual_memory(
        db=db,
        user_id=current_user.id,
        scope=payload.scope,
        kind=payload.kind,
        title=payload.title,
        detail=payload.detail,
        tags=payload.tags,
        confidence=payload.confidence,
        pinned=payload.pinned,
        active=payload.active,
        conversation_id=payload.conversation_id,
    )


def _update_memory_response(
    *,
    memory_id: int,
    payload: MemoryUpdate,
    request: Request,
    db: Session,
    current_user: User,
) -> MemoryItemOut:
    services = get_chat_services(request)
    memory = db.get(MemoryItem, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    if memory.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Memory not found")

    if payload.scope == "conversation":
        if payload.conversation_id is None:
            raise HTTPException(status_code=400, detail="Conversation memory requires conversation_id")
        if get_user_conversation(
            db,
            conversation_id=payload.conversation_id,
            user_id=current_user.id,
        ) is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

    return services.memory_service.update_manual_memory(
        db=db,
        memory=memory,
        user_id=current_user.id,
        scope=payload.scope,
        kind=payload.kind,
        title=payload.title,
        detail=payload.detail,
        tags=payload.tags,
        confidence=payload.confidence,
        pinned=payload.pinned,
        active=payload.active,
        conversation_id=payload.conversation_id,
    )


def _promote_memory_response(
    *,
    memory_id: int,
    payload: MemoryPromote,
    request: Request,
    db: Session,
    current_user: User,
) -> MemoryItemOut:
    services = get_chat_services(request)
    memory = db.get(MemoryItem, memory_id)
    if memory is None or memory.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    return services.memory_service.promote_memory(
        db=db,
        memory=memory,
        target_scope=payload.scope,
    )


def _dismiss_memory_response(
    *,
    memory_id: int,
    request: Request,
    db: Session,
    current_user: User,
) -> MemoryItemOut:
    services = get_chat_services(request)
    memory = db.get(MemoryItem, memory_id)
    if memory is None or memory.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    return services.memory_service.dismiss_memory(db=db, memory=memory)


def _delete_memory_response(
    *,
    memory_id: int,
    request: Request,
    db: Session,
    current_user: User,
) -> None:
    services = get_chat_services(request)
    memory = db.get(MemoryItem, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    if memory.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    services.memory_service.delete_memory(db=db, memory=memory)


@router.get("", response_model=MemoryCollectionOut)
def list_memories(
    request: Request,
    conversation_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    return _list_memories_response(
        request=request,
        conversation_id=conversation_id,
        db=db,
        current_user=current_user,
    )


@router.post("/items", response_model=MemoryItemOut)
def create_memory(
    payload: MemoryCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    return _create_memory_response(
        payload=payload,
        request=request,
        db=db,
        current_user=current_user,
    )


@router.patch("/items/{memory_id}", response_model=MemoryItemOut)
def update_memory(
    memory_id: int,
    payload: MemoryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    return _update_memory_response(
        memory_id=memory_id,
        payload=payload,
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/{memory_id}/promote", response_model=MemoryItemOut)
def promote_memory(
    memory_id: int,
    payload: MemoryPromote,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    return _promote_memory_response(
        memory_id=memory_id,
        payload=payload,
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/{memory_id}/dismiss", response_model=MemoryItemOut)
def dismiss_memory(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    return _dismiss_memory_response(
        memory_id=memory_id,
        request=request,
        db=db,
        current_user=current_user,
    )


@router.delete("/items/{memory_id}", status_code=204)
def delete_memory(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    _delete_memory_response(
        memory_id=memory_id,
        request=request,
        db=db,
        current_user=current_user,
    )
