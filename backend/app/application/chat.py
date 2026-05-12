from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..chat.state import ChatServices
from ..runtime.chat_runs import ActiveChatRunConflict, get_chat_run_registry
from ..runtime.streaming import ndjson_stream_response
from ..schemas import ReasoningProfileValue, RegenerateRequest, ToolMode
from ..storage.models import User
from .chat_preparation import (
    active_chat_run_conflict_detail,
    prepare_chat_stream_run_request,
    prepare_regeneration_run_request,
)


def _raise_active_run_conflict(exc: ActiveChatRunConflict) -> None:
    # 中文注释：并发窗口里 registry 仍可能先发现冲突，这里转成 409，避免冒泡成 500。
    raise HTTPException(
        status_code=409,
        detail=active_chat_run_conflict_detail(exc.active_run),
    ) from exc


async def regenerate_chat_response(
    *,
    current_user: User,
    services: ChatServices,
    payload: RegenerateRequest,
    request: Request,
    db: Session,
) -> StreamingResponse:
    registry = get_chat_run_registry(request)
    async with registry.guard_submission(payload.conversation_id):
        run_request = await prepare_regeneration_run_request(
            current_user=current_user,
            services=services,
            payload=payload,
            request=request,
            db=db,
        )
        try:
            stream = await registry.start_or_attach(
                app=request.app,
                run_request=run_request,
            )
        except ActiveChatRunConflict as exc:
            _raise_active_run_conflict(exc)
    return ndjson_stream_response(stream)


async def chat_stream_response(
    *,
    current_user: User,
    services: ChatServices,
    request: Request,
    db: Session,
    conversation_id: Optional[int],
    message: str,
    model: Optional[str],
    tool_mode: ToolMode,
    knowledge_folders: list[str],
    reasoning_profile: ReasoningProfileValue | None,
    files: list[UploadFile] | None,
) -> StreamingResponse:
    registry = get_chat_run_registry(request)

    async def _prepare_and_start() -> StreamingResponse:
        run_request = await prepare_chat_stream_run_request(
            current_user=current_user,
            services=services,
            request=request,
            db=db,
            conversation_id=conversation_id,
            message=message,
            model=model,
            tool_mode=tool_mode,
            knowledge_folders=knowledge_folders,
            reasoning_profile=reasoning_profile,
            files=files,
        )
        try:
            stream = await registry.start_or_attach(
                app=request.app,
                run_request=run_request,
            )
        except ActiveChatRunConflict as exc:
            _raise_active_run_conflict(exc)
        return ndjson_stream_response(stream)

    if conversation_id is None:
        return await _prepare_and_start()

    async with registry.guard_submission(conversation_id):
        return await _prepare_and_start()


async def stream_active_chat_response(
    *,
    request: Request,
    conversation_id: int,
    after_seq: int | None = None,
) -> StreamingResponse:
    stream = await get_chat_run_registry(request).attach_existing(
        conversation_id,
        after_seq=after_seq,
    )
    if stream is None:
        raise HTTPException(status_code=404, detail="No active chat run.")
    return ndjson_stream_response(stream)
