from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..chat.context import (
    append_message_attachments,
    clone_message_attachments,
    conversation_options,
    conversation_title,
    history_message_ids,
)
from ..chat.state import ChatServices
from ..core.config import settings
from ..providers import normalize_model, resolve_model_profile
from ..runtime.modes import get_mode_runtime
from ..schemas import RegenerateRequest
from ..storage.access import get_user_conversation
from ..storage.media import persist_uploaded_attachments, remove_media_files
from ..storage.models import Conversation, Message, User


async def regenerate_chat_response(
    *,
    current_user: User,
    services: ChatServices,
    payload: RegenerateRequest,
    request: Request,
    db: Session,
) -> StreamingResponse:
    conversation = get_user_conversation(
        db,
        conversation_id=payload.conversation_id,
        user_id=current_user.id,
        options=conversation_options(),
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if payload.model:
        profile = resolve_model_profile(payload.model)
        if profile is None:
            raise HTTPException(status_code=400, detail=f"Model not enabled: {payload.model}")
        if conversation.model != profile.id:
            conversation.model = profile.id
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
    else:
        profile = resolve_model_profile(conversation.model)
        if profile is None:
            raise HTTPException(status_code=400, detail=f"Model not enabled: {conversation.model}")

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

    chat_mode = get_mode_runtime("chat")
    return StreamingResponse(
        chat_mode.stream(
            "run",
            services=services,
            request=request,
            conversation_id=conversation.id,
            message_id=regenerated_user_message.id,
            model=conversation.model,
            history_message_ids=history_message_ids(history_messages),
            query=source_user.content,
            tool_mode=payload.tool_mode,
            requested_reasoning_profile=payload.reasoning_profile,
        ),
        media_type="application/x-ndjson",
    )


async def chat_stream_response(
    *,
    current_user: User,
    services: ChatServices,
    request: Request,
    db: Session,
    conversation_id: Optional[int],
    message: str,
    model: Optional[str],
    tool_mode,
    reasoning_profile,
    files,
) -> StreamingResponse:
    content = message.strip()
    uploads = files or []
    target_model = normalize_model((model or "").strip() or settings.default_model)

    profile = resolve_model_profile(target_model)
    if profile is None:
        raise HTTPException(status_code=400, detail=f"Model not enabled: {target_model}")

    if not content and not uploads:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    conversation: Optional[Conversation] = None
    if conversation_id is not None:
        conversation = get_user_conversation(
            db,
            conversation_id=conversation_id,
            user_id=current_user.id,
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

    conversation = db.get(
        Conversation,
        conversation.id,
        options=conversation_options(),
    )
    assert conversation is not None

    chat_mode = get_mode_runtime("chat")
    return StreamingResponse(
        chat_mode.stream(
            "run",
            services=services,
            request=request,
            conversation_id=conversation.id,
            message_id=user_message.id,
            model=conversation.model,
            history_message_ids=history_message_ids(list(conversation.messages)),
            query=content,
            tool_mode=tool_mode,
            requested_reasoning_profile=reasoning_profile,
        ),
        media_type="application/x-ndjson",
    )
