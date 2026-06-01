from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc, exists, func, select
from sqlalchemy.orm import Session, selectinload

from .models import Conversation, MemoryItem, Message, MessageAttachment, Run


@dataclass(frozen=True)
class ConversationSummaryRow:
    id: int
    project_id: int | None
    title: str
    model: str
    temporary_chat: bool
    updated_at: object
    last_message_preview: str


@dataclass(frozen=True)
class ConversationMessageWindow:
    messages: list[Message]
    loaded_message_count: int
    remaining_message_count: int
    total_message_count: int


def get_user_conversation(
    db: Session,
    *,
    conversation_id: int,
    user_id: int,
    options: list | None = None,
) -> Conversation | None:
    query = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user_id,
    )
    for option in options or []:
        query = query.options(option)
    return db.scalar(query)


def get_user_message(
    db: Session,
    *,
    message_id: int,
    user_id: int,
) -> Message | None:
    return db.scalar(
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.id == message_id,
            Conversation.user_id == user_id,
        )
    )


def list_conversation_messages_window(
    db: Session,
    *,
    conversation_id: int,
    limit: int,
    before_message_id: int | None = None,
) -> ConversationMessageWindow:
    bounded_limit = max(1, limit)
    message_query = (
        select(Message)
        .options(selectinload(Message.attachments))
        .where(Message.conversation_id == conversation_id)
    )
    if before_message_id is not None:
        message_query = message_query.where(Message.id < before_message_id)

    messages_desc = db.scalars(
        message_query
        .order_by(desc(Message.id))
        .limit(bounded_limit)
    ).all()
    messages = list(reversed(messages_desc))
    _hydrate_message_models(db, messages)
    _hydrate_pending_memories(db, messages)

    total_message_count = db.scalar(
        select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
    ) or 0

    if not messages:
        remaining_message_count = total_message_count if before_message_id is None else 0
    else:
        oldest_message_id = messages[0].id
        remaining_message_count = db.scalar(
            select(func.count(Message.id)).where(
                Message.conversation_id == conversation_id,
                Message.id < oldest_message_id,
            )
        ) or 0

    return ConversationMessageWindow(
        messages=messages,
        loaded_message_count=len(messages),
        remaining_message_count=max(0, remaining_message_count),
        total_message_count=total_message_count,
    )


def _hydrate_message_models(db: Session, messages: list[Message]) -> None:
    assistant_message_ids = [
        message.id
        for message in messages
        if message.role == "assistant" and getattr(message, "id", None) is not None
    ]
    if not assistant_message_ids:
        return

    run_rows = db.execute(
        select(Run.response_message_id, Run.model_id)
        .where(Run.response_message_id.in_(assistant_message_ids))
        .order_by(desc(Run.id))
    ).all()

    model_by_message_id: dict[int, str] = {}
    for response_message_id, model_id in run_rows:
        if response_message_id is None or response_message_id in model_by_message_id:
            continue
        model_by_message_id[response_message_id] = model_id

    for message in messages:
        setattr(message, "_resolved_model_id", model_by_message_id.get(message.id))


def _hydrate_pending_memories(db: Session, messages: list[Message]) -> None:
    assistant_message_ids = [
        message.id
        for message in messages
        if message.role == "assistant" and getattr(message, "id", None) is not None
    ]
    if not assistant_message_ids:
        return

    pending_items = db.scalars(
        select(MemoryItem)
        .where(
            MemoryItem.source_assistant_message_id.in_(assistant_message_ids),
            MemoryItem.status == "active",
            MemoryItem.active.is_(True),
            MemoryItem.confidence_state == "pending",
        )
        .order_by(MemoryItem.id.asc())
    ).all()
    pending_by_message_id: dict[int, list[MemoryItem]] = {}
    for item in pending_items:
        if item.source_assistant_message_id is None:
            continue
        pending_by_message_id.setdefault(item.source_assistant_message_id, []).append(item)

    for message in messages:
        setattr(message, "_pending_memories", pending_by_message_id.get(message.id, []))


def list_user_conversation_summaries(
    db: Session,
    *,
    user_id: int,
    project_id: int | None = None,
) -> list[ConversationSummaryRow]:
    latest_message_id = (
        select(Message.id)
        .where(Message.conversation_id == Conversation.id)
        .order_by(desc(Message.id))
        .limit(1)
        .correlate(Conversation)
        .scalar_subquery()
    )
    latest_message_content = (
        select(Message.content)
        .where(Message.id == latest_message_id)
        .correlate(Conversation)
        .scalar_subquery()
    )
    has_attachments = exists(select(1).where(MessageAttachment.message_id == latest_message_id))
    query = select(
        Conversation.id,
        Conversation.project_id,
        Conversation.title,
        Conversation.model,
        Conversation.temporary_chat,
        Conversation.updated_at,
        latest_message_content.label("last_message_content"),
        has_attachments.label("has_attachments"),
    ).where(Conversation.user_id == user_id)
    if project_id is not None:
        query = query.where(Conversation.project_id == project_id)
    rows = db.execute(query.order_by(desc(Conversation.updated_at), desc(Conversation.id))).all()

    summaries: list[ConversationSummaryRow] = []
    for row in rows:
        preview_content = (row.last_message_content or "").strip()
        preview = preview_content[:80] if preview_content else ("[Attachment]" if row.has_attachments else "")
        summaries.append(
            ConversationSummaryRow(
                id=row.id,
                project_id=row.project_id,
                title=row.title,
                model=row.model,
                temporary_chat=bool(row.temporary_chat),
                updated_at=row.updated_at,
                last_message_preview=preview,
            )
        )
    return summaries
