from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.config import settings
from ..llm import normalize_model
from ..retrieval import RetrievalMode
from ..schemas import RegenerateRequest
from ..storage.media import persist_uploaded_attachments, remove_media_files
from ..storage.models import Conversation, Message
from .context import (
    append_message_attachments,
    clone_message_attachments,
    conversation_options,
    conversation_title,
    history_message_ids,
)
from .state import ChatServices
from .streamer import response_event_stream


async def regenerate_chat_response(
    *,
    services: ChatServices,
    payload: RegenerateRequest,
    db: Session,
) -> StreamingResponse:
    conversation = db.get(
        Conversation,
        payload.conversation_id,
        options=conversation_options(),
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if payload.model and conversation.model != payload.model:
        conversation.model = payload.model
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    target_index = next(
        (
            index
            for index, message in enumerate(conversation.messages)
            if message.id == payload.assistant_message_id and message.role == "assistant"
        ),
        None,
    )
    if target_index is None:
        raise HTTPException(status_code=404, detail="Assistant message not found")

    source_user = next(
        (
            message
            for message in reversed(conversation.messages[:target_index])
            if message.role == "user"
        ),
        None,
    )
    if source_user is None:
        raise HTTPException(status_code=400, detail="Source user message not found")

    history_messages = list(conversation.messages[:target_index])
    regenerated_user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=source_user.content,
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

    return StreamingResponse(
        response_event_stream(
            services=services,
            conversation_id=conversation.id,
            message_id=regenerated_user_message.id,
            model=conversation.model,
            history_message_ids=history_message_ids(history_messages),
            query=source_user.content,
            retrieval_mode=payload.retrieval_mode,
            thinking_enabled=payload.thinking_enabled,
        ),
        media_type="application/x-ndjson",
    )


async def chat_stream_response(
    *,
    services: ChatServices,
    db: Session,
    conversation_id: Optional[int],
    message: str,
    model: Optional[str],
    retrieval_mode: RetrievalMode,
    thinking_enabled: Optional[bool],
    files,
) -> StreamingResponse:
    content = message.strip()
    uploads = files or []
    if not content and not uploads:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    conversation: Optional[Conversation] = None
    if conversation_id is not None:
        conversation = db.get(
            Conversation,
            conversation_id,
            options=conversation_options(),
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        uploaded_attachments = await persist_uploaded_attachments(uploads)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not content and not uploaded_attachments:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        if conversation is None:
            conversation = Conversation(
                title=conversation_title(content, len(uploaded_attachments)),
                model=model or normalize_model(settings.default_model),
            )
            db.add(conversation)
            db.flush()

        if model and conversation.model != model:
            conversation.model = model

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

    conversation = db.get(
        Conversation,
        conversation.id,
        options=conversation_options(),
    )
    assert conversation is not None

    return StreamingResponse(
        response_event_stream(
            services=services,
            conversation_id=conversation.id,
            message_id=user_message.id,
            model=conversation.model,
            history_message_ids=history_message_ids(list(conversation.messages)),
            query=content,
            retrieval_mode=retrieval_mode,
            thinking_enabled=thinking_enabled,
        ),
        media_type="application/x-ndjson",
    )
