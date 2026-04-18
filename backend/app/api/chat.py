from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..application import chat_stream_response, regenerate_chat_response
from ..auth import require_current_user
from ..chat.state import ChatServices, get_chat_services
from ..schemas import MessageFeedbackUpdate, ReasoningProfileValue, RegenerateRequest, ToolMode
from ..storage.database import get_db
from ..storage.models import Conversation, Message, User

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/regenerate")
async def regenerate_chat(
    payload: RegenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    return await regenerate_chat_response(
        current_user=current_user,
        services=services,
        payload=payload,
        request=request,
        db=db,
    )


@router.post("/stream")
async def chat_stream(
    request: Request,
    conversation_id: Optional[int] = Form(None),
    message: str = Form(""),
    model: Optional[str] = Form(None),
    tool_mode: ToolMode = Form("none"),
    reasoning_profile: Optional[ReasoningProfileValue] = Form(None),
    files: Optional[list[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    services = get_chat_services(request)
    return await chat_stream_response(
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


@router.patch("/messages/{message_id}/feedback")
async def update_message_feedback(
    message_id: int,
    payload: MessageFeedbackUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    message = db.scalar(
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.id == message_id,
            Message.role == "assistant",
            Conversation.user_id == current_user.id,
        )
    )
    if message is None or message.role != "assistant":
        raise HTTPException(status_code=404, detail="Assistant message not found")

    message.feedback_value = payload.value
    db.add(message)
    db.commit()
    db.refresh(message)
    return {"id": message.id, "feedback": message.feedback}
