from __future__ import annotations

from sqlalchemy import select

from ..storage.models import MemoryItem
from .store_utils import normalize_memory_text, utcnow
from .types import MemoryScope


class PendingMemoryStoreMixin:
    def list_pending_for_assistant_message(
        self,
        *,
        user_id: int,
        assistant_message_id: int,
    ) -> list[MemoryItem]:
        return self._db.scalars(
            select(MemoryItem)
            .where(
                MemoryItem.user_id == user_id,
                MemoryItem.source_assistant_message_id == assistant_message_id,
                MemoryItem.status == "active",
                MemoryItem.active.is_(True),
                MemoryItem.confidence_state == "pending",
            )
            .order_by(MemoryItem.id.asc())
        ).all()

    def confirm_pending_memory(
        self,
        memory: MemoryItem,
        *,
        user_id: int,
        scope: MemoryScope | None = None,
        kind: str | None = None,
        title: str | None = None,
        detail: str | None = None,
        tags: list[str] | tuple[str, ...] | None = None,
    ) -> MemoryItem:
        previous_conversation_id = memory.conversation_id
        if scope is not None:
            memory.scope = scope
        if kind is not None:
            memory.kind = kind
        if title is not None:
            memory.title = normalize_memory_text(title, max_length=255)
        if detail is not None:
            memory.detail = normalize_memory_text(detail, max_length=4000)
        if tags is not None:
            memory.tags_json = self.serialize_tags(tags)
        memory.confidence_state = "confirmed"
        memory.write_policy = "explicit"
        memory.source_type = "promoted"
        memory.status = "active"
        memory.active = True
        memory.last_confirmed_at = utcnow()
        memory.promoted_at = memory.promoted_at or utcnow()
        memory.updated_at = utcnow()
        memory.conversation_id = memory.conversation_id if memory.scope in {"conversation", "working"} else None
        self._db.add(memory)
        self._db.flush()
        self.reindex_memory(memory)
        # 中文注释：确认候选记忆后，当前会话摘要和可能迁出的旧摘要都要同步，避免上下文面板残留。
        self.rebuild_documents(user_id=user_id, conversation_id=memory.conversation_id)
        if previous_conversation_id != memory.conversation_id:
            self.rebuild_documents(user_id=user_id, conversation_id=previous_conversation_id)
        return memory

    def reject_pending_memory(self, memory: MemoryItem, *, user_id: int) -> MemoryItem:
        previous_conversation_id = memory.conversation_id
        memory.confidence_state = "rejected"
        memory.status = "archived"
        memory.active = False
        memory.updated_at = utcnow()
        self._db.add(memory)
        self._db.flush()
        self.reindex_memory(memory)
        # 中文注释：拒绝候选后重建摘要，让 pending 内容立即从后续 prompt 中消失。
        self.rebuild_documents(user_id=user_id, conversation_id=previous_conversation_id)
        return memory

