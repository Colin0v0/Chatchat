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
from .embedder import MemoryEmbedder
from .extractor import MemoryExtractor
from .normalizer import normalize_candidate, normalize_memory_fields
from .store import MemoryCollection, MemoryStore, utcnow
from .types import MemoryCandidate, MemoryPromptPayload, MemoryStatus, MemoryTurnPolicy, MemoryWorkspaceCollection, MemoryWritePolicy

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
GROOMING_MARKERS = (
    "谢谢",
    "感谢",
    "明白了",
    "好的",
    "知道了",
    "没问题",
    "ok",
    "okay",
    "thx",
    "thanks",
    "got it",
    "明白",
    "收到",
    "嗯",
    "哦",
    "啊",
    "好",
    "行",
    "可以",
)
TOKEN_PATTERN = re.compile(r"[0-9A-Za-z_\u4e00-\u9fff]{2,}")


class MemoryService:
    def __init__(self, settings: Settings):
        self._extractor = MemoryExtractor(extract_limit=settings.memory_extract_max_items)
        self._memory_model = settings.memory_model.strip()
        self._recall_limit = max(1, settings.memory_recall_top_k)
        self._refresh_semaphore = asyncio.Semaphore(max(1, settings.memory_refresh_max_concurrency))
        self._refresh_tasks: dict[int, asyncio.Task[None]] = {}
        self._embedding_enabled = bool(settings.memory_embedding_enabled)
        self._vector_weight = max(0.0, min(1.0, float(settings.memory_vector_weight)))
        self._keyword_weight = max(0.0, min(1.0, float(settings.memory_keyword_weight)))
        self._auto_memory_min_confidence = max(0.0, min(1.0, float(settings.memory_auto_promote_min_confidence)))
        self._embedder: MemoryEmbedder | None = None
        if self._embedding_enabled:
            try:
                self._embedder = MemoryEmbedder(settings)
            except Exception:
                logger.warning("Memory embedder initialization failed, disabling vector recall")
                self._embedding_enabled = False

    async def build_prompt_payload(
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

        query_embedding: list[float] | None = None
        if self._embedding_enabled and self._embedder is not None and query.strip():
            try:
                query_embedding = await self._embedder.embed_query(query)
            except Exception:
                logger.exception("memory query embedding failed, falling back to keyword recall")

        hits = store.recall(
            query=query,
            user_id=user_id,
            conversation_id=conversation_id,
            limit=self._recall_limit,
            query_embedding=query_embedding,
            vector_weight=self._vector_weight,
            keyword_weight=self._keyword_weight,
        )

        hit_items: list[MemoryItem] = []
        for hit in hits:
            item = store.get_by_id(hit.memory_id, user_id=user_id)
            if item is None or item.status != "active" or not item.active:
                continue
            hit_items.append(item)

        if not documents and not hit_items:
            return MemoryPromptPayload(debug={"memory_documents": 0, "memory_hits": 0})

        # Treat as fresh conversation if there are very few messages.
        from ..storage.models import Message
        from sqlalchemy import func as sql_func
        message_count = db.scalar(
            db.query(sql_func.count()).where(Message.conversation_id == conversation_id)
        ) or 0
        is_fresh = message_count <= 2

        payload_message = self._build_prompt_message(
            documents=documents, hit_items=hit_items, is_fresh_conversation=is_fresh
        )
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
        previous_task = self._refresh_tasks.get(conversation_id)
        task = asyncio.create_task(
            self._run_scheduled_refresh(
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                response_model=response_model,
            )
        )
        self._refresh_tasks[conversation_id] = task
        task.add_done_callback(
            lambda completed_task, tracked_conversation_id=conversation_id: self._finalize_refresh_task(
                conversation_id=tracked_conversation_id,
                task=completed_task,
            )
        )
        if previous_task is not None and previous_task is not task:
            previous_task.cancel()

    def _finalize_refresh_task(
        self,
        *,
        conversation_id: int,
        task: asyncio.Task[None],
    ) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("memory refresh task failed")
        finally:
            if self._refresh_tasks.get(conversation_id) is task:
                self._refresh_tasks.pop(conversation_id, None)

    async def _run_scheduled_refresh(
        self,
        *,
        conversation_id: int,
        user_message_id: int,
        assistant_message_id: int,
        response_model: str,
    ) -> None:
        async with self._refresh_semaphore:
            await self.refresh_from_turn(
                conversation_id=conversation_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                response_model=response_model,
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

            # Gather existing memories so the extractor can avoid duplicates
            # and detect updates/corrections.
            store = MemoryStore(db)
            existing_items = store.list_collection(
                user_id=conversation.user_id,
                conversation_id=conversation_id,
            )
            existing_memories: list[str] = []
            for item in existing_items.global_items:
                if item.status == "active" and item.active:
                    existing_memories.append(f"[{item.kind}] {item.title}: {item.detail}")
            for item in existing_items.conversation_items:
                if item.status == "active" and item.active:
                    existing_memories.append(f"[{item.kind}] {item.title}: {item.detail}")
            # Cap to avoid bloating the extraction prompt.
            existing_memories = existing_memories[:24]

            candidates = await self._extractor.extract(
                model=self._memory_model or response_model,
                conversation_title=conversation.title,
                user_message=user_message.content,
                assistant_message=assistant_message.content,
                existing_memories=existing_memories,
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

                embedding: list[float] | None = None
                if self._embedder is not None:
                    try:
                        embedding = await self._embedder.embed_memory(
                            title=resolved_candidate.title,
                            detail=resolved_candidate.detail,
                            tags=list(resolved_candidate.tags),
                        )
                    except Exception:
                        logger.exception("memory embedding failed during refresh, storing without vector")

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
                    embedding=embedding,
                    action=normalized.action,
                )
                if item is not None:
                    wrote_any = True

            store.rebuild_documents(user_id=conversation.user_id, conversation_id=conversation_id)
            if wrote_any:
                db.commit()
            else:
                db.commit()
        except asyncio.CancelledError:
            db.rollback()
            raise
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
        is_fresh_conversation: bool = False,
    ) -> ChatMessagePayload:
        lines = [
            "The following is what you know about the user from past conversations.",
            "Use this naturally—do not mention that you \"remember\" it unless it genuinely improves the response.",
            "Prefer the current conversation over this background if they conflict.",
        ]
        if is_fresh_conversation:
            lines.append(
                "If this is the very first exchange, greet the user briefly using what you know about them."
            )

        # Render documents (curated summaries like user_profile, workspace_profile, conversation_brief)
        if documents:
            for document in documents:
                lines.append("")
                lines.append(f"{document.title}:")
                lines.append(document.content)

        # Render hit_items as natural context (skip technical labels like [global/Profile])
        if hit_items:
            lines.append("")
            lines.append("Related context:")
            for item in hit_items:
                line = f"- {item.title}"
                if item.detail:
                    line += f": {item.detail}"
                time_hint = self._relative_time_hint(item.updated_at or item.created_at)
                if time_hint:
                    line += f" ({time_hint})"
                lines.append(line)

        return ChatMessagePayload(role="system", content="\n".join(lines).strip())

    def _relative_time_hint(self, dt: datetime | None) -> str:
        if dt is None:
            return ""
        now = utcnow()
        delta = now - dt
        if delta.days < 1:
            return "今天"
        if delta.days < 2:
            return "昨天"
        if delta.days < 7:
            return f"{delta.days} 天前"
        if delta.days < 30:
            weeks = delta.days // 7
            return f"{weeks} 周前"
        if delta.days < 365:
            months = delta.days // 30
            return f"{months} 个月前"
        years = delta.days // 365
        return f"{years} 年前"

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
            allow_automatic_storage=not explicit_request and not has_attachments,
            skip_due_to_attachments=has_attachments and not explicit_request,
            modality="attachment" if has_attachments else "text",
        )

    def _should_attempt_auto_memory(self, *, user_message: Message) -> bool:
        content = (user_message.content or "").strip()
        if len(content) < 8:
            return False
        tokens = TOKEN_PATTERN.findall(content)
        if len(tokens) < 2:
            return False
        # Skip grooming / low-information responses
        content_lower = content.casefold()
        if any(marker in content_lower for marker in GROOMING_MARKERS):
            # If the message is very short and only contains grooming words, skip
            if len(content) < 30:
                return False
        return True

    def _resolve_auto_memory(
        self,
        *,
        candidate,
        policy: MemoryTurnPolicy,
    ) -> tuple[MemoryCandidate, MemoryStatus, datetime | None, MemoryWritePolicy] | None:
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

        if not policy.allow_automatic_storage:
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

        if candidate.confidence < self._auto_memory_min_confidence:
            return None

        # 中文注释：长期信息达到阈值后直接写入全局长期记忆，不再经过额外确认层。
        return (
            MemoryCandidate(
                scope="global",
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

    def _looks_transient(self, candidate) -> bool:
        combined = " ".join([candidate.title, candidate.detail]).casefold()
        if any(marker in combined for marker in TRANSIENT_MARKERS):
            return True
        return candidate.kind in {"goal", "project", "constraint"}
