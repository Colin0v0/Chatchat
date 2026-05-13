from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..storage.models import ChatHistoryEntry, MemoryDocument, MemoryItem, UserMemorySettings
from .store_utils import utcnow
from .types import MemorySettingsState


class MemorySettingsStore:
    def __init__(self, db: Session):
        self._db = db

    def get_or_create(self, *, user_id: int) -> UserMemorySettings:
        settings = self._db.scalar(
            select(UserMemorySettings).where(UserMemorySettings.user_id == user_id)
        )
        if settings is not None:
            return settings
        # 中文注释：首次访问时创建用户级记忆开关，后续所有记忆写入和召回都读这一处。
        settings = UserMemorySettings(user_id=user_id)
        self._db.add(settings)
        self._db.flush()
        return settings

    def get_state(self, *, user_id: int) -> MemorySettingsState:
        settings = self.get_or_create(user_id=user_id)
        return MemorySettingsState(
            saved_memories_enabled=bool(settings.saved_memories_enabled),
            reference_chat_history_enabled=bool(settings.reference_chat_history_enabled),
            memory_learning_enabled=bool(settings.memory_learning_enabled),
            sensitive_memory_enabled=bool(settings.sensitive_memory_enabled),
        )

    def update(
        self,
        *,
        user_id: int,
        saved_memories_enabled: bool | None = None,
        reference_chat_history_enabled: bool | None = None,
        memory_learning_enabled: bool | None = None,
        sensitive_memory_enabled: bool | None = None,
    ) -> UserMemorySettings:
        settings = self.get_or_create(user_id=user_id)
        if saved_memories_enabled is not None:
            settings.saved_memories_enabled = bool(saved_memories_enabled)
        if reference_chat_history_enabled is not None:
            settings.reference_chat_history_enabled = bool(reference_chat_history_enabled)
        if memory_learning_enabled is not None:
            settings.memory_learning_enabled = bool(memory_learning_enabled)
        if sensitive_memory_enabled is not None:
            settings.sensitive_memory_enabled = bool(sensitive_memory_enabled)
        settings.updated_at = utcnow()
        self._db.add(settings)
        self._db.flush()
        return settings

    def clear_saved_memories(self, *, user_id: int) -> int:
        memory_ids = list(
            self._db.scalars(select(MemoryItem.id).where(MemoryItem.user_id == user_id))
        )
        if not memory_ids:
            return 0
        self._db.execute(delete(MemoryDocument).where(MemoryDocument.user_id == user_id))
        self._db.execute(delete(MemoryItem).where(MemoryItem.id.in_(memory_ids)))
        self._db.flush()
        return len(memory_ids)

    def clear_chat_history_index(self, *, user_id: int) -> int:
        entry_ids = list(
            self._db.scalars(select(ChatHistoryEntry.id).where(ChatHistoryEntry.user_id == user_id))
        )
        if not entry_ids:
            return 0
        self._db.execute(delete(ChatHistoryEntry).where(ChatHistoryEntry.id.in_(entry_ids)))
        self._db.flush()
        return len(entry_ids)
