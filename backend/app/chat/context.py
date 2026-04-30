from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core.config import settings
from ..storage.models import Conversation, Message, MessageAttachment
from .prompt_builder import HistoryWindow
from .title import generate_conversation_title, should_refresh_title
from .token_budget import estimate_text_tokens

MESSAGE_LOAD_OPTION = selectinload(Conversation.messages).selectinload(Message.attachments)


def save_assistant_message(
    *,
    db: Session,
    conversation: Conversation,
    content: str,
    reasoning: str | None = None,
    sources: list[dict[str, str | float | None]],
    context_payload: dict[str, object] | None = None,
) -> Message:
    source_user = next((message for message in conversation.messages if message.role == "user"), None)
    if source_user is not None and should_refresh_title(
        current_title=conversation.title,
        source_content=source_user.content,
        uploaded_count=len(source_user.attachments),
        max_length=settings.conversation_title_max_length,
    ):
        conversation.title = generate_conversation_title(
            content=source_user.content,
            uploaded_count=len(source_user.attachments),
            max_length=settings.conversation_title_max_length,
        )

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        reasoning_content=(reasoning or "").strip() or None,
        sources_json=json.dumps(sources, ensure_ascii=False),
        context_json=json.dumps(context_payload, ensure_ascii=False) if context_payload else None,
    )
    conversation.updated_at = datetime.now(timezone.utc)
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
    return generate_conversation_title(
        content=content,
        uploaded_count=uploaded_count,
        max_length=settings.conversation_title_max_length,
    )


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


def trim_history_messages(
    messages: list[Message],
    *,
    message_limit: int,
    token_budget: int,
) -> list[Message]:
    if not messages:
        return []

    max_messages = max(1, message_limit)
    max_tokens = max(1, token_budget)
    selected: list[Message] = []
    used_tokens = 0

    for message in reversed(messages):
        message_tokens = estimated_message_tokens(message)
        would_exceed_messages = len(selected) >= max_messages
        would_exceed_tokens = used_tokens > 0 and used_tokens + message_tokens > max_tokens
        if would_exceed_messages or would_exceed_tokens:
            break
        selected.append(message)
        used_tokens += message_tokens

    trimmed = list(reversed(selected))
    while len(trimmed) > 1 and trimmed[0].role == "assistant":
        trimmed.pop(0)
    return trimmed or [messages[-1]]


def select_history_window(
    messages: list[Message],
    *,
    message_limit: int,
    token_budget: int,
) -> HistoryWindow:
    recent_messages = trim_history_messages(
        messages,
        message_limit=message_limit,
        token_budget=token_budget,
    )
    recent_ids = {message.id for message in recent_messages if getattr(message, "id", None) is not None}
    older_messages = [
        message
        for message in messages
        if getattr(message, "id", None) is None or message.id not in recent_ids
    ]
    return HistoryWindow(
        older_messages=older_messages,
        recent_messages=recent_messages,
    )


def estimated_message_tokens(message: Message) -> int:
    parts = [
        message.content or "",
        message.attachment_context or "",
        message.image_context or "",
    ]
    attachments_weight = len(message.attachments) * 24
    return sum(estimate_text_tokens(part) for part in parts) + attachments_weight


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
