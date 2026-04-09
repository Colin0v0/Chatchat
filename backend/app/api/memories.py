from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..chat.state import get_chat_services
from ..schemas import MemoryCollectionOut, MemoryCreate, MemoryItemOut, MemoryUpdate
from ..storage.access import get_user_conversation
from ..storage.database import get_db
from ..storage.models import MemoryItem, User

router = APIRouter(prefix="/api/memories", tags=["memories"])


@router.get("", response_model=MemoryCollectionOut)
def list_memories(
    request: Request,
    conversation_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    if conversation_id is not None and get_user_conversation(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    ) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    collection = services.memory_service.list_collection(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
    )
    return MemoryCollectionOut(
        global_items=collection.global_items,
        conversation_items=collection.conversation_items,
    )


@router.post("", response_model=MemoryItemOut)
def create_memory(
    payload: MemoryCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
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


@router.patch("/{memory_id}", response_model=MemoryItemOut)
def update_memory(
    memory_id: int,
    payload: MemoryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
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


@router.delete("/{memory_id}", status_code=204)
def delete_memory(
    memory_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    memory = db.get(MemoryItem, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    if memory.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    services.memory_service.delete_memory(db=db, memory=memory)
