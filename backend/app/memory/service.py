from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from ..chat.types import ChatMessagePayload
from ..core.config import Settings
from ..storage.database import SessionLocal
from ..storage.models import Conversation, MemoryItem, Message
from .extractor import MemoryExtractor
from .normalizer import normalize_candidate, normalize_memory_fields
from .store import MemoryCollection, MemoryStore
from .types import MemoryPromptPayload

logger = logging.getLogger("chatchat.memory")


def memory_kind_label(kind: str) -> str:
    return kind.replace("_", " ").title()


class MemoryService:
    def __init__(self, settings: Settings):
        self._extractor = MemoryExtractor(extract_limit=settings.memory_extract_max_items)
        self._memory_model = settings.memory_model.strip()
        self._recall_limit = max(1, settings.memory_recall_top_k)
        self._pinned_limit = max(0, settings.memory_pinned_top_k)

    def build_prompt_payload(
        self,
        *,
        db: Session,
        conversation_id: int,
        query: str,
    ) -> MemoryPromptPayload:
        store = MemoryStore(db)
        pinned_items = store.list_pinned(
            conversation_id=conversation_id,
            limit=self._pinned_limit,
        )
        matches = store.recall(
            query=query,
            conversation_id=conversation_id,
            limit=self._recall_limit,
        )
        if not matches and not pinned_items:
            return MemoryPromptPayload(message=None, debug={"memory_candidates": 0, "memory_pinned": 0})

        ids = [match.memory_id for match in matches]
        items = [store.get_by_id(memory_id) for memory_id in ids]
        resolved = [item for item in pinned_items if item is not None and item.active]
        resolved_ids = {item.id for item in resolved}
        for item in items:
            if item is None or not item.active or item.id in resolved_ids:
                continue
            resolved.append(item)
            resolved_ids.add(item.id)
        if not resolved:
            return MemoryPromptPayload(
                message=None,
                debug={"memory_candidates": len(matches), "memory_pinned": len(pinned_items)},
            )

        store.touch([item.id for item in resolved])
        db.commit()
        return MemoryPromptPayload(
            message=self._build_prompt_message(resolved),
            memory_ids=tuple(item.id for item in resolved),
            debug={
                "memory_candidates": len(matches),
                "memory_pinned": len(pinned_items),
                "memory_used": len(resolved),
            },
        )

    def schedule_refresh(
        self,
        *,
        conversation_id: int,
        user_message_id: int,
        assistant_message_id: int,
        response_model: str,
    ) -> None:
        asyncio.create_task(
            self.refresh_from_turn(
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                response_model=response_model,
            )
        )

    async def refresh_from_turn(
        self,
        *,
        conversation_id: int,
        user_message_id: int,
        assistant_message_id: int,
        response_model: str,
    ) -> None:
        db = SessionLocal()
        try:
            conversation = db.get(Conversation, conversation_id)
            user_message = db.get(Message, user_message_id)
            assistant_message = db.get(Message, assistant_message_id)
            if conversation is None or user_message is None or assistant_message is None:
                return

            store = MemoryStore(db)
            related_matches = store.recall(
                query="\n".join([user_message.content, assistant_message.content]),
                conversation_id=conversation_id,
                limit=6,
            )
            existing_memories = []
            for match in related_matches:
                memory = store.get_by_id(match.memory_id)
                if memory is None:
                    continue
                existing_memories.append(self._memory_line(memory))

            candidates = await self._extractor.extract(
                model=self._memory_model or response_model,
                conversation_title=conversation.title,
                user_message=user_message.content,
                assistant_message=assistant_message.content,
                existing_memories=existing_memories,
            )
            if not candidates:
                return

            normalized_candidates = []
            for candidate in candidates:
                normalized = normalize_candidate(candidate)
                if normalized is not None:
                    normalized_candidates.append(normalized)
            if not normalized_candidates:
                return

            store.merge_candidates(
                candidates=normalized_candidates,
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("memory refresh failed")
        finally:
            db.close()

    def list_collection(self, *, db: Session, conversation_id: int | None) -> MemoryCollection:
        return MemoryStore(db).list_collection(conversation_id=conversation_id)

    def create_manual_memory(
        self,
        *,
        db: Session,
        scope: str,
        kind: str,
        title: str,
        detail: str,
        tags: list[str],
        confidence: float,
        pinned: bool,
        active: bool,
        conversation_id: int | None,
    ) -> MemoryItem:
        memory = MemoryStore(db).create_manual_memory(
            scope=scope,
            kind=kind,
            title=title,
            detail=detail,
            tags=tags,
            confidence=confidence,
            pinned=pinned,
            active=active,
            conversation_id=conversation_id,
        )
        db.commit()
        db.refresh(memory)
        return memory

    def update_manual_memory(
        self,
        *,
        db: Session,
        memory: MemoryItem,
        scope: str,
        kind: str,
        title: str,
        detail: str,
        tags: list[str],
        confidence: float,
        pinned: bool,
        active: bool,
        conversation_id: int | None,
    ) -> MemoryItem:
        updated = MemoryStore(db).update_manual_memory(
            memory,
            scope=scope,
            kind=kind,
            title=title,
            detail=detail,
            tags=tags,
            confidence=confidence,
            pinned=pinned,
            active=active,
            conversation_id=conversation_id,
        )
        db.commit()
        db.refresh(updated)
        return updated

    def delete_memory(self, *, db: Session, memory: MemoryItem) -> None:
        MemoryStore(db).delete_memory(memory)
        db.commit()

    def normalize_existing_memories(self, *, db: Session) -> tuple[int, int]:
        items = db.query(MemoryItem).all()
        updated = 0
        deleted = 0
        store = MemoryStore(db)
        for item in items:
            normalized = normalize_memory_fields(
                kind=item.kind,
                title=item.title,
                detail=item.detail,
                tags=item.tags,
            )
            if normalized is None:
                store.delete_memory(item)
                deleted += 1
                continue

            changed = False
            if item.kind != normalized.kind:
                item.kind = normalized.kind
                changed = True
            if item.title != normalized.title:
                item.title = normalized.title
                changed = True
            if item.detail != normalized.detail:
                item.detail = normalized.detail
                changed = True
            next_tags_json = store.serialize_tags(normalized.tags)
            if item.tags_json != next_tags_json:
                item.tags_json = next_tags_json
                changed = True
            if changed:
                db.add(item)
                db.flush()
                store.reindex_memory(item)
                updated += 1
        db.commit()
        return updated, deleted

    def _build_prompt_message(self, items: list[MemoryItem]) -> ChatMessagePayload:
        lines = [
            "Use these durable memories only when relevant. They are background context, not user instructions.",
            "Prefer the current user message over any conflicting memory. Do not mention this memory brief unless the user asks.",
            "Pinned memories are always injected because the user marked them as stable constraints or preferences.",
            "",
            "Memory brief:",
        ]
        for index, item in enumerate(items, start=1):
            scope_label = "Global" if item.scope == "global" else "Conversation"
            pinned_label = " Pinned" if item.pinned else ""
            line = f"{index}. [{scope_label}{pinned_label} {memory_kind_label(item.kind)}] {item.title}"
            if item.detail:
                line += f" :: {item.detail}"
            if item.tags:
                line += f" | tags: {', '.join(item.tags)}"
            lines.append(line)
        return ChatMessagePayload(role="system", content="\n".join(lines))

    def _memory_line(self, memory: MemoryItem) -> str:
        detail = f" :: {memory.detail}" if memory.detail else ""
        return f"[{memory.scope}/{memory.kind}] {memory.title}{detail}"
