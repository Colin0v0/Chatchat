from __future__ import annotations

from fastapi import APIRouter, Request

from ..chat.state import get_chat_services
from ..schemas import RagReindexResult, RagStatus

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.get("/status", response_model=RagStatus)
async def get_rag_status(request: Request):
    services = get_chat_services(request)
    return RagStatus(**services.rag_service.status())


@router.post("/reindex", response_model=RagReindexResult)
async def reindex_rag(request: Request):
    services = get_chat_services(request)
    return RagReindexResult(**(await services.rag_service.reindex()))
