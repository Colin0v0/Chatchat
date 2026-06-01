from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..chat.context import conversation_media_paths, conversation_options, message_preview
from ..core.config import settings
from ..projects import require_user_project
from ..providers import normalize_model, resolve_model_profile
from ..runtime.chat_runs import get_chat_run_registry
from ..schemas import (
    ChatActiveRunOut,
    ConversationCreate,
    ConversationDetail,
    ConversationMessagePage,
    ConversationSummary,
    ConversationUpdate,
)
from ..storage.access import (
    get_user_conversation,
    list_conversation_messages_window,
    list_user_conversation_summaries,
)
from ..storage.database import get_db
from ..storage.media import remove_media_files
from ..storage.models import Conversation, ImageGenerationJob, MemoryItem, Run, RunEvent, User

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


async def _conversation_active_run(request: Request, conversation_id: int) -> ChatActiveRunOut | None:
    payload = await get_chat_run_registry(request).describe(conversation_id)
    if payload is None:
        return None
    started_at = payload.get("started_at")
    run_id = payload.get("run_id")
    last_seq = payload.get("last_seq")
    return ChatActiveRunOut(
        action=str(payload.get("action", "")).strip(),
        run_id=run_id.strip() if isinstance(run_id, str) and run_id.strip() else "",
        last_seq=last_seq if isinstance(last_seq, int) else None,
        started_at=started_at.strip() if isinstance(started_at, str) and started_at.strip() else None,
    )


@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    project_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    require_user_project(db, user_id=current_user.id, project_id=project_id)
    return [
        ConversationSummary(
            id=item.id,
            project_id=item.project_id,
            title=item.title,
            model=item.model,
            temporary_chat=item.temporary_chat,
            updated_at=item.updated_at,
            last_message_preview=item.last_message_preview,
        )
        for item in list_user_conversation_summaries(db, user_id=current_user.id, project_id=project_id)
    ]


@router.post("", response_model=ConversationSummary)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    project = require_user_project(db, user_id=current_user.id, project_id=payload.project_id)
    target_model = payload.model or (project.default_model if project is not None else None) or normalize_model(settings.default_model)
    if settings.model_catalog_strict and resolve_model_profile(target_model) is None:
        raise HTTPException(status_code=400, detail=f"Model not enabled: {target_model}")

    conversation = Conversation(
        user_id=current_user.id,
        project_id=payload.project_id,
        title=payload.title,
        model=target_model,
        temporary_chat=payload.temporary_chat,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ConversationSummary(
        id=conversation.id,
        project_id=conversation.project_id,
        title=conversation.title,
        model=conversation.model,
        temporary_chat=conversation.temporary_chat,
        updated_at=conversation.updated_at,
        last_message_preview="",
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: int,
    request: Request,
    message_limit: int = Query(default=settings.conversation_view_message_limit, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    conversation = get_user_conversation(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    window = list_conversation_messages_window(
        db,
        conversation_id=conversation_id,
        limit=message_limit,
    )
    return ConversationDetail(
        id=conversation.id,
        project_id=conversation.project_id,
        title=conversation.title,
        model=conversation.model,
        temporary_chat=conversation.temporary_chat,
        messages=window.messages,
        total_message_count=window.total_message_count,
        loaded_message_count=window.loaded_message_count,
        remaining_message_count=window.remaining_message_count,
        active_run=await _conversation_active_run(request, conversation.id),
    )


@router.get("/{conversation_id}/messages", response_model=ConversationMessagePage)
def get_conversation_messages(
    conversation_id: int,
    before_message_id: int = Query(..., ge=1),
    limit: int = Query(default=settings.conversation_view_message_limit, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    conversation = get_user_conversation(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    window = list_conversation_messages_window(
        db,
        conversation_id=conversation_id,
        limit=limit,
        before_message_id=before_message_id,
    )
    return ConversationMessagePage(
        messages=window.messages,
        loaded_message_count=window.loaded_message_count,
        remaining_message_count=window.remaining_message_count,
    )


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    conversation = get_user_conversation(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        options=conversation_options(),
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.title = payload.title.strip()
    conversation.updated_at = datetime.now(timezone.utc)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return ConversationSummary(
        id=conversation.id,
        project_id=conversation.project_id,
        title=conversation.title,
        model=conversation.model,
        temporary_chat=conversation.temporary_chat,
        updated_at=conversation.updated_at,
        last_message_preview=message_preview(conversation.messages[-1] if conversation.messages else None),
    )


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    conversation = get_user_conversation(
        db,
        conversation_id=conversation_id,
        user_id=current_user.id,
        options=conversation_options(),
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    remove_media_files(conversation_media_paths(conversation))
    message_ids = [message.id for message in conversation.messages if getattr(message, "id", None) is not None]
    run_filters = [Run.conversation_id == conversation_id]
    if message_ids:
        run_filters.extend(
            [
                Run.request_message_id.in_(message_ids),
                Run.response_message_id.in_(message_ids),
            ]
        )
    run_ids = list(db.scalars(select(Run.id).where(or_(*run_filters))))
    if run_ids:
        db.execute(delete(RunEvent).where(RunEvent.run_id.in_(run_ids)))
        db.execute(delete(Run).where(Run.id.in_(run_ids)))
    db.execute(
        delete(MemoryItem).where(
            MemoryItem.conversation_id == conversation_id,
            MemoryItem.user_id == current_user.id,
        )
    )
    db.execute(delete(ImageGenerationJob).where(ImageGenerationJob.conversation_id == conversation_id))
    db.delete(conversation)
    db.commit()
