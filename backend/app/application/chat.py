from __future__ import annotations

from typing import Optional

from fastapi import Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..chat.state import ChatServices
from ..schemas import ReasoningProfileValue, RegenerateRequest, ToolMode
from ..storage.models import User
from .chat_preparation import (
    prepare_chat_stream_run_request,
    prepare_regeneration_run_request,
)
from .streaming import stream_mode_action


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
    return stream_mode_action(
        mode_name="chat",
        action="run",
        request=run_request,
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
    return stream_mode_action(
        mode_name="chat",
        action="run",
        request=run_request,
    )
