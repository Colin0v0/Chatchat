from __future__ import annotations

from typing import Optional

from fastapi import Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..chat.state import ChatServices
from ..runtime.chat_runs import get_chat_run_registry
from ..runtime.streaming import ndjson_stream_response
from ..schemas import ReasoningProfileValue, RegenerateRequest, ToolMode
from ..storage.models import User
from .chat_preparation import (
    prepare_chat_stream_run_request,
    prepare_regeneration_run_request,
)


async def regenerate_chat_response(
    *,
    current_user: User,
    services: ChatServices,
    payload: RegenerateRequest,
    request: Request,
    db: Session,
) -> StreamingResponse:
    run_request = prepare_regeneration_run_request(
        current_user=current_user,
        services=services,
        payload=payload,
        request=request,
        db=db,
    )
    stream = await get_chat_run_registry(request).start_or_attach(
        app=request.app,
        run_request=run_request,
    )
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
    reasoning_profile: ReasoningProfileValue | None,
    files: list[UploadFile] | None,
) -> StreamingResponse:
    run_request = await prepare_chat_stream_run_request(
        current_user=current_user,
        services=services,
        request=request,
        db=db,
        conversation_id=conversation_id,
        message=message,
        model=model,
        tool_mode=tool_mode,
        reasoning_profile=reasoning_profile,
        files=files,
    )
    stream = await get_chat_run_registry(request).start_or_attach(
        app=request.app,
        run_request=run_request,
    )
    return ndjson_stream_response(stream)


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
        raise RuntimeError("No active chat run.")
    return ndjson_stream_response(stream)
