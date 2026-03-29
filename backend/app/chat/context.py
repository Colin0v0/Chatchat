from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..storage.models import Conversation, Message, MessageAttachment

MESSAGE_LOAD_OPTION = selectinload(Conversation.messages).selectinload(Message.attachments)


def save_assistant_message(
    *,
    db: Session,
    conversation: Conversation,
    content: str,
    sources: list[dict[str, str | float | None]],
) -> Message:
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        sources_json=json.dumps(sources, ensure_ascii=False),
    )
    conversation.updated_at = datetime.utcnow()
    db.add(assistant_message)
    db.add(conversation)
    db.commit()
    db.refresh(assistant_message)
    return assistant_message


def conversation_options() -> list:
    return [MESSAGE_LOAD_OPTION]


def message_preview(message: Optional[Message]) -> str:
    if message is None:
        return ""
    content = message.content.strip()
    if content:
        return content[:80]
    if message.attachments:
        return "[Attachment]"
    return ""


def conversation_title(content: str, uploaded_count: int) -> str:
    normalized = content.strip()
    if normalized:
        return normalized[:48]
    if uploaded_count:
        return "Attachment chat"
    return "New chat"


def conversation_media_paths(conversation: Conversation) -> list[str]:
    return [attachment.relative_path for message in conversation.messages for attachment in message.attachments]


def history_message_ids(messages: list[Message]) -> list[int]:
    return [message.id for message in messages]


def latest_user_query(message_history: list[dict[str, str]], fallback: str) -> str:
    for message in reversed(message_history):
        if message.get("role") == "user":
            content = message.get("content", "").strip()
            if content:
                return content
    return fallback.strip()


def load_history_messages(db: Session, message_ids: list[int]) -> list[Message]:
    if not message_ids:
        return []

    loaded_messages = db.scalars(
        select(Message)
        .options(selectinload(Message.attachments))
        .where(Message.id.in_(message_ids))
    ).all()
    messages_by_id = {message.id: message for message in loaded_messages}
    return [messages_by_id[message_id] for message_id in message_ids if message_id in messages_by_id]


def append_message_attachments(*, db: Session, message: Message, attachments) -> None:
    for position, attachment in enumerate(attachments):
        db.add(
            MessageAttachment(
                message_id=message.id,
                kind=attachment.kind,
                original_name=attachment.original_name,
                mime_type=attachment.mime_type,
                relative_path=attachment.relative_path,
                size_bytes=attachment.size_bytes,
                extension=attachment.extension,
                position=position,
            )
        )


def clone_message_attachments(*, db: Session, source: Message, target: Message) -> None:
    for position, attachment in enumerate(source.attachments):
        db.add(
            MessageAttachment(
                message_id=target.id,
                kind=attachment.kind,
                original_name=attachment.original_name,
                mime_type=attachment.mime_type,
                relative_path=attachment.relative_path,
                size_bytes=attachment.size_bytes,
                extension=attachment.extension,
                position=position,
            )
        )
