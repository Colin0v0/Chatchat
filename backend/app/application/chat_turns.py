from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..chat.context import append_message_attachments, clone_message_attachments, conversation_title
from ..providers import ModelProfile, normalize_model, resolve_model_profile
from ..storage.media import StoredAttachment, remove_media_files
from ..storage.models import Conversation, Message, User


@dataclass(frozen=True)
class PersistedChatTurn:
    conversation: Conversation
    user_message: Message


def resolve_chat_model(*, requested_model: Optional[str], fallback_model: str) -> ModelProfile:
    target_model = normalize_model((requested_model or "").strip() or fallback_model)
    profile = resolve_model_profile(target_model)
    if profile is None:
        raise HTTPException(status_code=400, detail=f"Model not enabled: {target_model}")
    return profile


def persist_chat_turn(
    *,
    db: Session,
    current_user: User,
    conversation: Conversation | None,
    profile: ModelProfile,
    content: str,
    uploaded_attachments: list[StoredAttachment],
) -> PersistedChatTurn:
    try:
        if conversation is None:
            conversation = Conversation(
                user_id=current_user.id,
                title=conversation_title(content, len(uploaded_attachments)),
                model=profile.id,
            )
            db.add(conversation)
            db.flush()

        if conversation.model != profile.id:
            conversation.model = profile.id

        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=content,
        )
        conversation.updated_at = datetime.utcnow()
        db.add(user_message)
        db.flush()
        append_message_attachments(db=db, message=user_message, attachments=uploaded_attachments)
        db.add(conversation)
        db.commit()
        db.refresh(user_message)
    except Exception:
        remove_media_files([attachment.relative_path for attachment in uploaded_attachments])
        db.rollback()
        raise

    return PersistedChatTurn(conversation=conversation, user_message=user_message)


def persist_regenerated_turn(
    *,
    db: Session,
    conversation: Conversation,
    source_user: Message,
    override_content: str | None = None,
) -> Message:
    regenerated_user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=source_user.content if override_content is None else override_content,
        image_context=source_user.image_context,
        attachment_context=source_user.attachment_context,
    )
    conversation.updated_at = datetime.utcnow()
    db.add(regenerated_user_message)
    db.flush()
    clone_message_attachments(db=db, source=source_user, target=regenerated_user_message)
    db.add(conversation)
    db.commit()
    db.refresh(regenerated_user_message)
    return regenerated_user_message
