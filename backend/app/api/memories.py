from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..chat.state import get_chat_services
from ..schemas import (
    MemoryCollectionOut,
    MemoryCreate,
    MemoryClearResult,
    MemoryItemOut,
    MemoryLayerCollectionOut,
    MemorySettingsOut,
    MemorySettingsUpdate,
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


@router.get("/settings", response_model=MemorySettingsOut)
def get_memory_settings(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    return services.memory_service.get_settings(db=db, user_id=current_user.id)


@router.patch("/settings", response_model=MemorySettingsOut)
def update_memory_settings(
    payload: MemorySettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    return services.memory_service.update_settings(
        db=db,
        user_id=current_user.id,
        saved_memories_enabled=payload.saved_memories_enabled,
        reference_chat_history_enabled=payload.reference_chat_history_enabled,
        memory_learning_enabled=payload.memory_learning_enabled,
        sensitive_memory_enabled=payload.sensitive_memory_enabled,
    )


@router.post("/clear-saved", response_model=MemoryClearResult)
def clear_saved_memories(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    return MemoryClearResult(
        deleted_count=services.memory_service.clear_saved_memories(db=db, user_id=current_user.id)
    )


@router.post("/clear-history-index", response_model=MemoryClearResult)
def clear_chat_history_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    return MemoryClearResult(
        deleted_count=services.memory_service.clear_chat_history_index(db=db, user_id=current_user.id)
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
