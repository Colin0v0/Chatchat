from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..chat.context import conversation_media_paths, conversation_options, message_preview
from ..core.config import settings
from ..llm.catalog import resolve_model_route
from ..llm import normalize_model
from ..schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationMessagePage,
    ConversationSummary,
    ConversationUpdate,
)
from ..storage.access import (
    get_user_conversation,
    list_conversation_messages_window,
    list_user_conversation_summaries,
)
from ..storage.database import get_db
from ..storage.media import remove_media_files
from ..storage.models import Conversation, MemoryItem, User

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    return [
        ConversationSummary(
            id=item.id,
            title=item.title,
            model=item.model,
            updated_at=item.updated_at,
            last_message_preview=item.last_message_preview,
        )
        for item in list_user_conversation_summaries(db, user_id=current_user.id)
    ]


@router.post("", response_model=ConversationSummary)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    target_model = payload.model or normalize_model(settings.default_model)
    if settings.model_catalog_strict and resolve_model_route(target_model) is None:
        raise HTTPException(status_code=400, detail=f"Model not enabled: {target_model}")

    conversation = Conversation(
        user_id=current_user.id,
        title=payload.title,
        model=target_model,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        model=conversation.model,
        updated_at=conversation.updated_at,
        last_message_preview="",
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int,
    message_limit: int = Query(default=settings.conversation_view_message_limit, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    conversation = get_user_conversation(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    window = list_conversation_messages_window(
        db,
        conversation_id=conversation_id,
        limit=message_limit,
    )
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        model=conversation.model,
        messages=window.messages,
        total_message_count=window.total_message_count,
        loaded_message_count=window.loaded_message_count,
        remaining_message_count=window.remaining_message_count,
    )


@router.get("/{conversation_id}/messages", response_model=ConversationMessagePage)
def get_conversation_messages(
    conversation_id: int,
    before_message_id: int = Query(..., ge=1),
    limit: int = Query(default=settings.conversation_view_message_limit, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    conversation = get_user_conversation(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    window = list_conversation_messages_window(
        db,
        conversation_id=conversation_id,
        limit=limit,
        before_message_id=before_message_id,
    )
    return ConversationMessagePage(
        messages=window.messages,
        loaded_message_count=window.loaded_message_count,
        remaining_message_count=window.remaining_message_count,
    )


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    conversation = get_user_conversation(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        options=conversation_options(),
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.title = payload.title.strip()
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        model=conversation.model,
        updated_at=conversation.updated_at,
        last_message_preview=message_preview(conversation.messages[-1] if conversation.messages else None),
    )


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    conversation = get_user_conversation(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        options=conversation_options(),
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    remove_media_files(conversation_media_paths(conversation))
    db.execute(
        delete(MemoryItem).where(
            MemoryItem.conversation_id == conversation_id,
            MemoryItem.user_id == current_user.id,
        )
    )
    db.delete(conversation)
    db.commit()
