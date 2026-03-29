from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from ..chat.state import ChatServices, get_chat_services
from ..chat.workflow import chat_stream_response, regenerate_chat_response
from ..schemas import RegenerateRequest, RetrievalMode
from ..storage.database import get_db

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
        db=db,
        conversation_id=conversation_id,
        message=message,
        model=model,
        retrieval_mode=retrieval_mode,
        thinking_enabled=thinking_enabled,
        files=files,
    )
