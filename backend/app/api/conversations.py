from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..chat.context import conversation_media_paths, conversation_options, message_preview, MESSAGE_LOAD_OPTION
from ..core.config import settings
from ..llm import normalize_model
from ..schemas import ConversationCreate, ConversationDetail, ConversationSummary, ConversationUpdate
from ..storage.database import get_db
from ..storage.media import remove_media_files
from ..storage.models import Conversation

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
def list_conversations(db: Session = Depends(get_db)):
    conversations = db.scalars(
        select(Conversation)
        .options(MESSAGE_LOAD_OPTION)
        .order_by(desc(Conversation.updated_at), desc(Conversation.id))
    ).all()

    items: list[ConversationSummary] = []
    for conversation in conversations:
        items.append(
            ConversationSummary(
                id=conversation.id,
                title=conversation.title,
                model=conversation.model,
                updated_at=conversation.updated_at,
                last_message_preview=message_preview(conversation.messages[-1] if conversation.messages else None),
            )
        )
    return items


@router.post("", response_model=ConversationSummary)
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db)):
    conversation = Conversation(
        title=payload.title,
        model=payload.model or normalize_model(settings.default_model),
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
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.get(
        Conversation,
        conversation_id,
        options=conversation_options(),
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
):
    conversation = db.get(
        Conversation,
        conversation_id,
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
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id, options=conversation_options())
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    remove_media_files(conversation_media_paths(conversation))
    db.delete(conversation)
    db.commit()
