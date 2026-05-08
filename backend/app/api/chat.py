from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..application import chat_stream_response, regenerate_chat_response, stream_active_chat_response
from ..auth import require_current_user
from ..chat.state import ChatServices, get_chat_services
from ..runtime.chat_runs import get_chat_run_registry
from ..schemas import MessageFeedbackUpdate, ReasoningProfileValue, RegenerateRequest, ToolMode
from ..storage.database import get_db
from ..storage.models import Conversation, Message, User

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatStreamCancelRequest(BaseModel):
    conversation_id: int = Field(ge=1)


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
    knowledge_folders: Optional[list[str]] = Form(None),
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
        knowledge_folders=knowledge_folders or [],
        reasoning_profile=reasoning_profile,
        files=files,
    )


@router.post("/stream/cancel")
async def cancel_chat_stream(
    payload: ChatStreamCancelRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == payload.conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 中文注释：前端 Stop 会调用这里，真正取消后台 run，避免下一次发送撞上残留 active run。
    cancelled = await get_chat_run_registry(request).cancel(conversation.id)
    return {"cancelled": cancelled}


@router.get("/stream/active")
async def stream_active_chat(
    request: Request,
    conversation_id: int = Query(..., ge=1),
    run_id: Optional[str] = Query(default=None),
    after_seq: Optional[int] = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    active_run = await get_chat_run_registry(request).describe(conversation_id)
    if active_run is None:
        raise HTTPException(status_code=404, detail="No active chat run")
    current_run_id = active_run.get("run_id")
    if run_id and isinstance(current_run_id, str) and current_run_id != run_id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ActiveRunMismatch",
                "message": "Active chat run changed. Refresh the conversation and reconnect.",
            },
        )
    return await stream_active_chat_response(
        request=request,
        conversation_id=conversation_id,
        after_seq=after_seq,
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
