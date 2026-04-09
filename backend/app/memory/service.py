from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..chat.types import ChatMessagePayload
from ..core.config import Settings
from ..storage.database import SessionLocal
from ..storage.models import Conversation, MemoryDocument, MemoryItem, Message
from .extractor import MemoryExtractor
from .normalizer import normalize_candidate, normalize_memory_fields
from .store import MemoryCollection, MemoryStore
from .types import MemoryCandidate, MemoryPromptPayload, MemoryTurnPolicy, MemoryWorkspaceCollection

logger = logging.getLogger("chatchat.memory")

EXPLICIT_MEMORY_MARKERS = (
    "记住",
    "记下来",
    "加入记忆",
    "加入全局记忆",
    "以后都",
    "以后默认",
    "长期记住",
    "remember this",
    "save this memory",
)
GLOBAL_MEMORY_MARKERS = (
    "全局",
    "长期",
    "以后都",
    "以后默认",
    "跨会话",
    "一直",
    "always",
    "across chats",
)
TRANSIENT_MARKERS = (
    "这次",
    "本次",
    "当前",
    "先",
    "暂时",
    "目前",
    "this time",
    "for now",
    "current",
    "temporary",
)
TOKEN_PATTERN = re.compile(r"[0-9A-Za-z_\u4e00-\u9fff]{2,}")


def memory_kind_label(kind: str) -> str:
    return kind.replace("_", " ").title()


class MemoryService:
    def __init__(self, settings: Settings):
        self._extractor = MemoryExtractor(extract_limit=settings.memory_extract_max_items)
        self._memory_model = settings.memory_model.strip()
        self._recall_limit = max(1, settings.memory_recall_top_k)

    def build_prompt_payload(
        self,
        *,
        db: Session,
        user_id: int,
        conversation_id: int,
        query: str,
    ) -> MemoryPromptPayload:
        if user_id <= 0:
            return MemoryPromptPayload()

        store = MemoryStore(db)
        store.expire_stale_working_memory(user_id=user_id)
        documents = store.list_documents(user_id=user_id, conversation_id=conversation_id)
        hits = store.recall(
            query=query,
            user_id=user_id,
            conversation_id=conversation_id,
            limit=self._recall_limit,
        )

        hit_items: list[MemoryItem] = []
        for hit in hits:
            item = store.get_by_id(hit.memory_id, user_id=user_id)
            if item is None or item.status != "active" or not item.active:
                continue
            hit_items.append(item)

        if not documents and not hit_items:
            return MemoryPromptPayload(debug={"memory_documents": 0, "memory_hits": 0})

        payload_message = self._build_prompt_message(documents=documents, hit_items=hit_items)
        if hit_items:
            store.touch([item.id for item in hit_items], user_id=user_id)
            db.commit()
        return MemoryPromptPayload(
            messages=(payload_message,),
            debug={
                "memory_documents": len(documents),
                "memory_hits": len(hit_items),
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
            if conversation.user_id is None:
                return

            policy = self._build_turn_policy(user_message=user_message)
            if policy.skip_due_to_attachments:
                MemoryStore(db).rebuild_documents(user_id=conversation.user_id, conversation_id=conversation_id)
                db.commit()
                return

            if not policy.explicit_request and not self._should_attempt_auto_memory(user_message=user_message):
                MemoryStore(db).rebuild_documents(user_id=conversation.user_id, conversation_id=conversation_id)
                db.commit()
                return

            candidates = await self._extractor.extract(
                model=self._memory_model or response_model,
                conversation_title=conversation.title,
                user_message=user_message.content,
                assistant_message=assistant_message.content,
                existing_memories=[],
            )
            if not candidates:
                MemoryStore(db).rebuild_documents(user_id=conversation.user_id, conversation_id=conversation_id)
                db.commit()
                return

            store = MemoryStore(db)
            wrote_any = False
            for candidate in candidates:
                normalized = normalize_candidate(candidate)
                if normalized is None:
                    continue
                resolved = self._resolve_auto_memory(
                    candidate=normalized,
                    policy=policy,
                )
                if resolved is None:
                    continue
                resolved_candidate, status, expires_at, write_policy = resolved
                item = store.upsert_auto_memory(
                    candidate=resolved_candidate,
                    user_id=conversation.user_id,
                    conversation_id=conversation_id,
                    status=status,
                    source_type="auto" if not policy.explicit_request else "promoted",
                    modality=policy.modality,
                    write_policy=write_policy,
                    pinned=False,
                    expires_at=expires_at,
                    user_message_id=user_message_id,
                    assistant_message_id=assistant_message_id,
                )
                if item is not None:
                    wrote_any = True

            store.rebuild_documents(user_id=conversation.user_id, conversation_id=conversation_id)
            if wrote_any:
                db.commit()
            else:
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("memory refresh failed")
        finally:
            db.close()

    def list_workspace(
        self,
        *,
        db: Session,
        user_id: int,
        conversation_id: int | None,
    ) -> MemoryWorkspaceCollection:
        return MemoryStore(db).list_workspace(user_id=user_id, conversation_id=conversation_id)

    def list_collection(
        self,
        *,
        db: Session,
        user_id: int,
        conversation_id: int | None,
    ) -> MemoryCollection:
        return MemoryStore(db).list_collection(user_id=user_id, conversation_id=conversation_id)

    def create_manual_memory(
        self,
        *,
        db: Session,
        user_id: int,
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
            user_id=user_id,
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
        user_id: int,
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
            user_id=user_id,
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

    def promote_memory(
        self,
        *,
        db: Session,
        memory: MemoryItem,
        target_scope: str | None,
    ) -> MemoryItem:
        promoted = MemoryStore(db).promote_candidate(memory, target_scope=target_scope)
        db.commit()
        db.refresh(promoted)
        return promoted

    def dismiss_memory(self, *, db: Session, memory: MemoryItem) -> MemoryItem:
        dismissed = MemoryStore(db).dismiss_candidate(memory)
        db.commit()
        db.refresh(dismissed)
        return dismissed

    def normalize_existing_memories(self, *, db: Session) -> tuple[int, int]:
        items = db.query(MemoryItem).all()
        updated = 0
        deleted = 0
        store = MemoryStore(db)
        touched_pairs: set[tuple[int, int | None]] = set()
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
                if item.user_id is not None:
                    touched_pairs.add((item.user_id, item.conversation_id))
        for user_id, conversation_id in touched_pairs:
            store.rebuild_documents(user_id=user_id, conversation_id=conversation_id)
        db.commit()
        return updated, deleted

    def _build_prompt_message(
        self,
        *,
        documents: list[MemoryDocument],
        hit_items: list[MemoryItem],
    ) -> ChatMessagePayload:
        lines = [
            "Use the following user-exclusive memory context as background guidance.",
            "Prefer the current conversation over memory if they conflict.",
            "Memory documents are curated summaries; relevant memory hits are precise retrieved notes.",
        ]

        if documents:
            lines.append("")
            lines.append("Memory documents:")
            for document in documents:
                lines.append(f"- {document.title}")
                lines.append(document.content)
                lines.append("")

        if hit_items:
            lines.append("Relevant memory hits:")
            for index, item in enumerate(hit_items, start=1):
                line = f"{index}. [{item.scope}/{memory_kind_label(item.kind)}] {item.title}"
                if item.detail:
                    line += f" :: {item.detail}"
                lines.append(line)

        return ChatMessagePayload(role="system", content="\n".join(lines).strip())

    def _build_turn_policy(self, *, user_message: Message) -> MemoryTurnPolicy:
        content = (user_message.content or "").strip().casefold()
        explicit_request = any(marker in content for marker in EXPLICIT_MEMORY_MARKERS)
        has_attachments = bool(user_message.attachments)
        target_scope = None
        if explicit_request:
            target_scope = "global" if any(marker in content for marker in GLOBAL_MEMORY_MARKERS) else "conversation"
        return MemoryTurnPolicy(
            explicit_request=explicit_request,
            target_scope=target_scope,
            allow_global=target_scope == "global",
            allow_auto_candidates=not explicit_request and not has_attachments,
            store_working_memory=not explicit_request and not has_attachments,
            skip_due_to_attachments=has_attachments and not explicit_request,
            modality="attachment" if has_attachments else "text",
            write_policy="explicit" if explicit_request else "auto_candidate",
        )

    def _should_attempt_auto_memory(self, *, user_message: Message) -> bool:
        content = (user_message.content or "").strip()
        if len(content) < 8:
            return False
        tokens = TOKEN_PATTERN.findall(content)
        return len(tokens) >= 2

    def _resolve_auto_memory(
        self,
        *,
        candidate,
        policy: MemoryTurnPolicy,
    ) -> tuple[MemoryCandidate, str, datetime | None, str] | None:
        if policy.explicit_request:
            return (
                MemoryCandidate(
                    scope=policy.target_scope or "conversation",
                    kind=candidate.kind,
                    title=candidate.title,
                    detail=candidate.detail,
                    tags=candidate.tags,
                    confidence=candidate.confidence,
                ),
                "active",
                None,
                "explicit",
            )

        if not policy.allow_auto_candidates:
            return None

        if self._looks_transient(candidate):
            return (
                MemoryCandidate(
                    scope="working",
                    kind=candidate.kind,
                    title=candidate.title,
                    detail=candidate.detail,
                    tags=candidate.tags,
                    confidence=candidate.confidence,
                ),
                "active",
                utcnow() + timedelta(days=2),
                "session",
            )

        return (
            MemoryCandidate(
                scope="conversation",
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                tags=candidate.tags,
                confidence=candidate.confidence,
            ),
            "candidate",
            None,
            "auto_candidate",
        )

    def _looks_transient(self, candidate) -> bool:
        combined = " ".join([candidate.title, candidate.detail]).casefold()
        if any(marker in combined for marker in TRANSIENT_MARKERS):
            return True
        return candidate.kind in {"goal", "project", "constraint"}
