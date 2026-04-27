from __future__ import annotations

from fastapi import HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..chat.state import ChatServices
from ..core.config import settings
from ..multimodal.file_types import resolve_attachment_type
from ..providers.catalog import ModelProfile
from ..runtime.requests import ChatRunRequest
from ..schemas import ReasoningProfileValue, RegenerateRequest, ToolMode
from ..storage.media import persist_uploaded_attachments
from ..storage.models import User
from .chat_requests import (
    build_chat_run_request,
    ensure_conversation_run_model,
    load_user_chat_conversation,
    reload_conversation_for_run,
    resolve_regeneration_source,
)
from .chat_turns import persist_chat_turn, persist_regenerated_turn, resolve_chat_model


def _ensure_chat_input_present(*, content: str, upload_count: int) -> None:
    if not content and upload_count == 0:
        raise HTTPException(status_code=400, detail="Message cannot be empty")


def _ensure_uploads_supported_by_model(*, profile: ModelProfile, uploads: list[UploadFile]) -> None:
    for upload in uploads:
        try:
            attachment_type = resolve_attachment_type(
                getattr(upload, "filename", "") or "",
                getattr(upload, "content_type", "") or "",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if attachment_type.kind == "image" and not profile.capabilities.input_image:
            raise HTTPException(
                status_code=400,
                detail="The selected model does not support image uploads.",
            )
        if attachment_type.extension == ".pdf" and not profile.capabilities.input_pdf:
            raise HTTPException(
                status_code=400,
                detail="The selected model does not support PDF uploads.",
            )
        if attachment_type.kind == "file" and attachment_type.extension != ".pdf" and not profile.capabilities.input_other_file:
            raise HTTPException(
                status_code=400,
                detail="The selected model does not support file uploads.",
            )


def _ensure_persisted_attachments_supported_by_model(*, profile: ModelProfile, attachments) -> None:
    for attachment in attachments:
        kind = getattr(attachment, "kind", "")
        extension = str(getattr(attachment, "extension", "")).lower()
        if kind == "image" and not profile.capabilities.input_image:
            raise HTTPException(
                status_code=400,
                detail="The selected model does not support image uploads.",
            )
        if extension == ".pdf" and not profile.capabilities.input_pdf:
            raise HTTPException(
                status_code=400,
                detail="The selected model does not support PDF uploads.",
            )
        if kind == "file" and extension != ".pdf" and not profile.capabilities.input_other_file:
            raise HTTPException(
                status_code=400,
                detail="The selected model does not support file uploads.",
            )


async def prepare_chat_stream_run_request(
    *,
    current_user: User,
    services: ChatServices,
    request: Request,
    db: Session,
    conversation_id: int | None,
    message: str,
    model: str | None,
    tool_mode: ToolMode,
    reasoning_profile: ReasoningProfileValue | None,
    files: list[UploadFile] | None,
) -> ChatRunRequest:
    content = message.strip()
    uploads = files or []
    _ensure_chat_input_present(content=content, upload_count=len(uploads))
    profile = resolve_chat_model(
        requested_model=model,
        fallback_model=settings.default_model,
    )
    _ensure_uploads_supported_by_model(profile=profile, uploads=uploads)

    conversation = (
        load_user_chat_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=current_user.id,
        )
        if conversation_id is not None
        else None
    )

    try:
        uploaded_attachments = await persist_uploaded_attachments(uploads)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _ensure_chat_input_present(content=content, upload_count=len(uploaded_attachments))
    persisted_turn = persist_chat_turn(
        db=db,
        current_user=current_user,
        conversation=conversation,
        profile=profile,
        content=content,
        uploaded_attachments=uploaded_attachments,
    )
    conversation = reload_conversation_for_run(
        db=db,
        conversation_id=persisted_turn.conversation.id,
    )
    return build_chat_run_request(
        services=services,
        request=request,
        conversation=conversation,
        user_message=persisted_turn.user_message,
        history_messages=list(conversation.messages),
        query=content,
        tool_mode=tool_mode,
        reasoning_profile=reasoning_profile,
    )


def prepare_regeneration_run_request(
    *,
    current_user: User,
    services: ChatServices,
    payload: RegenerateRequest,
    request: Request,
    db: Session,
) -> ChatRunRequest:
    edited_content = payload.edited_content.strip() if payload.edited_content is not None else None
    conversation = load_user_chat_conversation(
        db=db,
        conversation_id=payload.conversation_id,
        user_id=current_user.id,
    )
    ensure_conversation_run_model(
        db=db,
        conversation=conversation,
        requested_model=payload.model,
    )
    profile = resolve_chat_model(
        requested_model=payload.model or conversation.model,
        fallback_model=conversation.model,
    )
    regeneration = resolve_regeneration_source(
        conversation=conversation,
        assistant_message_id=payload.assistant_message_id,
    )
    _ensure_persisted_attachments_supported_by_model(
        profile=profile,
        attachments=regeneration.source_user.attachments,
    )
    query = regeneration.source_user.content if edited_content is None else edited_content
    _ensure_chat_input_present(
        content=query,
        upload_count=len(regeneration.source_user.attachments),
    )
    regenerated_user_message = persist_regenerated_turn(
        db=db,
        conversation=conversation,
        source_user=regeneration.source_user,
        override_content=edited_content,
    )
    return build_chat_run_request(
        services=services,
        request=request,
        conversation=conversation,
        user_message=regenerated_user_message,
        history_messages=regeneration.history_messages,
        query=query,
        tool_mode=payload.tool_mode,
        reasoning_profile=payload.reasoning_profile,
    )
