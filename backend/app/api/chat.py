from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..chat.state import ChatServices, get_chat_services
from ..chat.workflow import chat_stream_response, regenerate_chat_response
from ..schemas import MessageFeedbackUpdate, RegenerateRequest, RetrievalMode
from ..storage.database import get_db
from ..storage.models import Message

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/regenerate")
async def regenerate_chat(
    payload: RegenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    services = get_chat_services(request)
    return await regenerate_chat_response(
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
    retrieval_mode: RetrievalMode = Form("none"),
    thinking_enabled: Optional[bool] = Form(None),
    files: Optional[list[UploadFile]] = File(None),
    db: Session = Depends(get_db),
):
    services = get_chat_services(request)
    return await chat_stream_response(
        services=services,
        request=request,
        db=db,
        conversation_id=conversation_id,
        message=message,
        model=model,
        retrieval_mode=retrieval_mode,
        thinking_enabled=thinking_enabled,
        files=files,
    )


@router.patch("/messages/{message_id}/feedback")
async def update_message_feedback(
    message_id: int,
    payload: MessageFeedbackUpdate,
    db: Session = Depends(get_db),
):
    message = db.get(Message, message_id)
    if message is None or message.role != "assistant":
        raise HTTPException(status_code=404, detail="Assistant message not found")

    message.feedback_value = payload.value
    db.add(message)
    db.commit()
    db.refresh(message)
    return {"id": message.id, "feedback": message.feedback}
