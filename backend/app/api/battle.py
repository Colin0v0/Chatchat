from __future__ import annotations

import json
from dataclasses import dataclass, field
from collections.abc import AsyncIterator
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..chat.context import append_message_attachments
from ..chat.history import MessageHistoryService
from ..chat.types import ChatMessagePayload
from ..chat.state import get_chat_services
from ..multimodal.file_types import resolve_attachment_type
from ..runtime.model_runner import stream_model_response
from ..schemas import BattleStreamRequest, ReasoningProfileValue, ToolMode
from ..providers import resolve_model_profile
from ..storage.database import get_db
from ..storage.media import media_url, persist_uploaded_attachments
from ..storage.models import Conversation, Message, User
from ..tools import ToolContextBuildRequest, ToolPlanRequest, build_tool_policy

router = APIRouter(prefix="/api/battle", tags=["battle"])


@dataclass(frozen=True)
class BattlePreparedPrompt:
    messages: list[ChatMessagePayload]
    refusal_message: str | None = None
    sources: list[dict[str, str | float | None]] | None = None
    attachments: list[dict[str, object]] = field(default_factory=list)


def _ndjson(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _ensure_battle_input_present(*, content: str, upload_count: int) -> None:
    if not content and upload_count == 0:
        raise HTTPException(status_code=400, detail="Message cannot be empty")


def _ensure_uploads_supported_by_model(*, model: str, uploads: list[UploadFile]) -> None:
    profile = resolve_model_profile(model)
    if profile is None:
        raise HTTPException(status_code=400, detail="Model is not enabled in catalog.")

    for upload in uploads:
        try:
            attachment_type = resolve_attachment_type(
                getattr(upload, "filename", "") or "",
                getattr(upload, "content_type", "") or "",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if attachment_type.kind == "image" and not profile.capabilities.input_image:
            raise HTTPException(status_code=400, detail="The selected model does not support image uploads.")
        if attachment_type.extension == ".pdf" and not profile.capabilities.input_pdf:
            raise HTTPException(status_code=400, detail="The selected model does not support PDF uploads.")
        if attachment_type.kind == "file" and attachment_type.extension != ".pdf" and not profile.capabilities.input_other_file:
            raise HTTPException(status_code=400, detail="The selected model does not support file uploads.")


async def _prepare_battle_prompt(
    *,
    db: Session,
    payload: BattleStreamRequest,
    request: Request,
    current_user: User,
    uploads: list[UploadFile],
) -> BattlePreparedPrompt:
    content = payload.message.strip()
    _ensure_battle_input_present(content=content, upload_count=len(uploads))
    _ensure_uploads_supported_by_model(model=payload.model, uploads=uploads)
    profile = resolve_model_profile(payload.model)
    if profile is None:
        raise HTTPException(status_code=400, detail="Model is not enabled in catalog.")

    saved_attachments = await persist_uploaded_attachments(uploads)
    _ensure_battle_input_present(content=content, upload_count=len(saved_attachments))

    services = get_chat_services(request)
    conversation = Conversation(user_id=None, title="Battle prompt", model=payload.model)
    db.add(conversation)
    db.flush()
    message = Message(conversation_id=conversation.id, role="user", content=content)
    db.add(message)
    db.flush()
    append_message_attachments(db=db, message=message, attachments=saved_attachments)
    db.commit()
    db.refresh(message)

    try:
        # Battle 不落普通会话，但复用聊天链路的附件解析、RAG 和 Web 上下文构造。
        history_messages = [message]
        history_service = MessageHistoryService(db, services.attachment_context_service)
        prepared_history = await history_service.prepare(model=payload.model, messages=history_messages)
        prepared_retrieval_history = await history_service.prepare_retrieval_history(
            model=payload.model,
            messages=history_messages,
        )
        tool_policy = build_tool_policy(payload.tool_mode, knowledge_folders=payload.knowledge_folders)
        tool_plan = services.tool_runtime.plan_context(
            request=ToolPlanRequest(query=content, tool_policy=tool_policy),
        )
        include_file_context = len(saved_attachments) > 0
        prompt_context = await services.tool_runtime.build_context_payload(
            request=ToolContextBuildRequest(
                db=db,
                user_id=current_user.id,
                query=content,
                plan=tool_plan,
                retrieval_messages=prepared_retrieval_history.messages,
                conversation_messages=history_messages,
                include_file_context=include_file_context,
                include_image_context=profile.native_multimodal_mode == "false",
            ),
        )

        if prompt_context.should_refuse and prompt_context.refusal_message:
            return BattlePreparedPrompt(
                messages=[],
                refusal_message=prompt_context.refusal_message,
                sources=prompt_context.sources,
            )

        history_payloads = [
            ChatMessagePayload(role=m["role"], content=m["content"])
            for m in payload.history
        ]
        messages = [
            *([prompt_context.context_message] if prompt_context.context_message else []),
            *history_payloads,
            *prepared_history.messages,
        ]
        attachments = [
            {
                "id": f"battle-{attachment.relative_path.replace('/', '-')}"
                if attachment.relative_path
                else f"battle-{hash(attachment.original_name)}",
                "kind": attachment.kind,
                "original_name": attachment.original_name,
                "mime_type": attachment.mime_type,
                "size_bytes": attachment.size_bytes,
                "extension": attachment.extension,
                "url": media_url(attachment.relative_path),
            }
            for attachment in saved_attachments
        ]
        return BattlePreparedPrompt(messages=messages, sources=prompt_context.sources, attachments=attachments)
    finally:
        db.delete(conversation)
        db.commit()


async def _battle_event_stream(payload: BattleStreamRequest, prepared: BattlePreparedPrompt) -> AsyncIterator[str]:
    content_parts: list[str] = []
    yield _ndjson({"type": "meta", "model": payload.model})
    if prepared.attachments:
        yield _ndjson({"type": "attachments", "attachments": prepared.attachments})
    if prepared.sources:
        yield _ndjson({"type": "sources", "sources": prepared.sources})

    if prepared.refusal_message:
        yield _ndjson({"type": "token", "content": prepared.refusal_message})
        yield _ndjson({"type": "done", "content": prepared.refusal_message})
        return

    try:
        # Battle 模式不写入普通会话，只把同一个问题发给指定模型做匿名对比。
        async for chunk in stream_model_response(
            model=payload.model,
            messages=prepared.messages,
            requested_reasoning_profile=payload.reasoning_profile,
        ):
            if chunk.reasoning_delta:
                yield _ndjson({"type": "reasoning", "content": chunk.reasoning_delta})
            if chunk.output_text_delta:
                content_parts.append(chunk.output_text_delta)
                yield _ndjson({"type": "token", "content": chunk.output_text_delta})
            if chunk.done:
                yield _ndjson({"type": "done", "content": "".join(content_parts).strip()})
                return
    except Exception as exc:
        yield _ndjson({"type": "error", "message": str(exc)})


@router.post("/stream")
async def battle_stream(
    request: Request,
    message: str = Form(""),
    model: str = Form(...),
    tool_mode: ToolMode = Form("none"),
    knowledge_folders: Optional[list[str]] = Form(None),
    reasoning_profile: Optional[ReasoningProfileValue] = Form(None),
    history: Optional[str] = Form(None),
    files: Optional[list[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    parsed_history = json.loads(history) if history else []
    payload = BattleStreamRequest(
        message=message,
        model=model,
        tool_mode=tool_mode,
        knowledge_folders=knowledge_folders or [],
        reasoning_profile=reasoning_profile,
        history=parsed_history,
    )
    prepared = await _prepare_battle_prompt(
        db=db,
        payload=payload,
        request=request,
        current_user=current_user,
        uploads=files or [],
    )

    return StreamingResponse(
        _battle_event_stream(payload, prepared),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )
