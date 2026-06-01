from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..storage.database import get_db
from ..storage.media import (
    normalize_media_relative_path,
    resolve_media_file_path,
)
from ..storage.models import Conversation, Message, MessageAttachment, User

router = APIRouter(prefix="/media", tags=["media"])


def _message_attachment_belongs_to_user(*, db: Session, user_id: int, relative_path: str) -> bool:
    attachment_id = db.scalar(
        select(MessageAttachment.id)
        .join(Message, MessageAttachment.message_id == Message.id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            MessageAttachment.relative_path == relative_path,
            Conversation.user_id == user_id,
        )
        .limit(1)
    )
    return attachment_id is not None


def _battle_attachment_belongs_to_user(*, user_id: int, relative_path: str) -> bool:
    # 中文注释：新的 Battle 附件写入 battle/{user_id}/ 命名空间，流式返回后无需等快照落库即可访问。
    return relative_path.startswith(f"battle/{user_id}/")


def _user_can_read_media_path(*, db: Session, user_id: int, relative_path: str) -> bool:
    return _message_attachment_belongs_to_user(
        db=db,
        user_id=user_id,
        relative_path=relative_path,
    ) or _battle_attachment_belongs_to_user(
        user_id=user_id,
        relative_path=relative_path,
    )


@router.get("/{relative_path:path}")
def get_media_file(
    relative_path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    try:
        normalized_path = normalize_media_relative_path(relative_path)
        file_path = resolve_media_file_path(normalized_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Media file not found") from exc

    if not _user_can_read_media_path(db=db, user_id=current_user.id, relative_path=normalized_path):
        raise HTTPException(status_code=404, detail="Media file not found")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Media file not found")

    return FileResponse(file_path)
