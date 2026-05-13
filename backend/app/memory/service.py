from __future__ import annotations

import asyncio
import logging

from sqlalchemy.orm import Session

from ..core.config import Settings
from ..storage.database import SessionLocal
from ..storage.models import Conversation, MemoryItem, Message
from .embedder import MemoryEmbedder
from .extractor import MemoryExtractor
from .governance import filter_sensitive_candidates, is_sensitive_text
from .history_store import ChatHistoryRecallStore
from .history_summary import PastChatSummarizer, build_turn_index_text
from .normalizer import normalize_candidate, normalize_memory_fields
from .policy import MemoryPolicyMixin
from .prompt_payload import MemoryPromptPayloadMixin
from .settings_store import MemorySettingsStore
from .store import MemoryCollection, MemoryStore
from .types import (
    MemoryPromptPayload,
    MemorySettingsState,
    MemoryWorkspaceCollection,
)

logger = logging.getLogger("chatchat.memory")


class MemoryService(MemoryPromptPayloadMixin, MemoryPolicyMixin):
    def __init__(self, settings: Settings):
        self._extractor = MemoryExtractor(extract_limit=settings.memory_extract_max_items)
        self._memory_model = settings.memory_model.strip()
        self._recall_limit = max(1, settings.memory_recall_top_k)
        self._refresh_semaphore = asyncio.Semaphore(max(1, settings.memory_refresh_max_concurrency))
        self._refresh_tasks: dict[int, asyncio.Task[None]] = {}
        self._refresh_locks: dict[int, asyncio.Lock] = {}
        self._embedding_enabled = bool(settings.memory_embedding_enabled)
        self._vector_weight = max(0.0, min(1.0, float(settings.memory_vector_weight)))
        self._keyword_weight = max(0.0, min(1.0, float(settings.memory_keyword_weight)))
        self._auto_memory_min_confidence = max(0.0, min(1.0, float(settings.memory_auto_promote_min_confidence)))
        self._past_chat_recall_limit = max(1, int(getattr(settings, "memory_past_chat_recall_top_k", 4)))
        self._summarizer = PastChatSummarizer(model=self._memory_model)
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

        settings_state = MemorySettingsStore(db).get_state(user_id=user_id)
        conversation = db.get(Conversation, conversation_id)
        if conversation is not None and conversation.temporary_chat:
            return MemoryPromptPayload(debug={"memory_disabled": True, "temporary_chat": True})
        if not settings_state.saved_memories_enabled and not settings_state.reference_chat_history_enabled:
            return MemoryPromptPayload(debug={"memory_disabled": True})

        store = MemoryStore(db)
        documents = []
        hit_items: list[MemoryItem] = []
        if settings_state.saved_memories_enabled:
            store.expire_stale_working_memory(user_id=user_id)
            documents = store.list_documents(user_id=user_id, conversation_id=conversation_id)
        else:
            store.expire_stale_working_memory(user_id=user_id)

        query_embedding: list[float] | None = None
        if self._embedding_enabled and self._embedder is not None and query.strip():
            try:
                query_embedding = await self._embedder.embed_query(query)
            except Exception:
                logger.exception("memory query embedding failed")

        if settings_state.saved_memories_enabled:
            hits = store.recall(
                query=query,
                user_id=user_id,
                conversation_id=conversation_id,
                limit=self._recall_limit,
                query_embedding=query_embedding,
                vector_weight=self._vector_weight,
                keyword_weight=self._keyword_weight,
            )

            for hit in hits:
                item = store.get_by_id(hit.memory_id, user_id=user_id)
                if item is None or item.status != "active" or not item.active:
                    continue
                if item.confidence_state not in {"inferred", "confirmed"}:
                    continue
                hit_items.append(item)

        past_chat_refs = []
        dynamic_recap = ""
        if settings_state.reference_chat_history_enabled:
            past_chat_refs = ChatHistoryRecallStore(db).recall(
                query=query,
                user_id=user_id,
                conversation_id=conversation_id,
                limit=self._past_chat_recall_limit,
                query_embedding=query_embedding,
                vector_weight=self._vector_weight,
                keyword_weight=self._keyword_weight,
            )
            if past_chat_refs:
                dynamic_recap = await self._summarizer.synthesize_dynamic_recap(
                    query=query,
                    snippets=[reference.summary or reference.excerpt for reference in past_chat_refs],
                )

        if not documents and not hit_items and not past_chat_refs:
            return MemoryPromptPayload(
                debug={
                    "memory_documents": 0,
                    "memory_hits": 0,
                    "past_chat_hits": 0,
                    "memory_settings": self._settings_debug(settings_state),
                }
            )

        # Treat as fresh conversation if there are very few messages.
        from ..storage.models import Message
        from sqlalchemy import func as sql_func
        message_count = db.scalar(
            db.query(sql_func.count()).where(Message.conversation_id == conversation_id)
        ) or 0
        is_fresh = message_count <= 2

        payload_message = self._build_prompt_message(
            documents=documents,
            hit_items=hit_items,
            past_chat_refs=past_chat_refs,
            dynamic_recap=dynamic_recap,
            is_fresh_conversation=is_fresh,
        )
        if hit_items:
            store.touch([item.id for item in hit_items], user_id=user_id)
        if past_chat_refs:
            ChatHistoryRecallStore(db).touch(
                user_id=user_id,
                entry_ids=[reference.id for reference in past_chat_refs],
            )
        if hit_items or past_chat_refs:
            db.commit()
        query_hints = self._build_query_hints(hit_items=hit_items, past_chat_refs=past_chat_refs)
        return MemoryPromptPayload(
            messages=(payload_message,),
            query_hints=tuple(query_hints),
            debug={
                "memory_documents": len(documents),
                "memory_document_references": [
                    self._prompt_memory_document_payload(document)
                    for document in documents
                ],
                "memory_hits": len(hit_items),
                "memory_items": [
                    self._prompt_memory_item_payload(item)
                    for item in sorted(hit_items, key=self._prompt_item_sort_key)
                ],
                "past_chat_hits": len(past_chat_refs),
                "past_chat_references": [
                    self._prompt_past_chat_payload(reference)
                    for reference in past_chat_refs
                ],
                "past_chat_dynamic_recap": dynamic_recap,
                "memory_query_hints": query_hints,
                "memory_settings": self._settings_debug(settings_state),
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

    async def wait_for_refresh_idle(self, *, conversation_id: int) -> None:
        task = self._refresh_tasks.get(conversation_id)
        if task is not None:
            await task

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
                self._refresh_locks.pop(conversation_id, None)

    async def _run_scheduled_refresh(
        self,
        *,
        conversation_id: int,
        user_message_id: int,
        assistant_message_id: int,
        response_model: str,
    ) -> None:
        lock = self._refresh_locks.setdefault(conversation_id, asyncio.Lock())
        # 中文注释：同一会话的记忆刷新按完成顺序排队，避免后一轮刷新取消前一轮导致记忆丢失。
        async with lock:
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
            if conversation.temporary_chat:
                return

            settings_state = MemorySettingsStore(db).get_state(user_id=conversation.user_id)
            turn_index_text = build_turn_index_text(
                conversation_title=conversation.title,
                user_message=user_message.content,
                assistant_message=assistant_message.content,
            )
            if not settings_state.sensitive_memory_enabled and is_sensitive_text(turn_index_text):
                # 中文注释：敏感内容默认不进入历史索引，也不送给记忆抽取模型。
                MemoryStore(db).rebuild_documents(user_id=conversation.user_id, conversation_id=conversation_id)
                db.commit()
                return

            history_embedding: list[float] | None = None
            if settings_state.reference_chat_history_enabled and settings_state.memory_learning_enabled:
                summary = await self._summarizer.summarize_turn(
                    conversation_title=conversation.title,
                    user_message=user_message.content,
                    assistant_message=assistant_message.content,
                )
                embedding_text = summary.strip() if summary.strip() else turn_index_text
                if self._embedder is not None and embedding_text.strip():
                    try:
                        history_embedding = await self._embedder.embed_query(embedding_text)
                    except Exception:
                        logger.exception("past chat embedding failed during refresh")
                ChatHistoryRecallStore(db).upsert_turn(
                    user_id=conversation.user_id,
                    conversation=conversation,
                    user_message=user_message,
                    assistant_message=assistant_message,
                    summary=summary,
                    embedding=history_embedding,
                )

            if not settings_state.memory_learning_enabled:
                MemoryStore(db).rebuild_documents(user_id=conversation.user_id, conversation_id=conversation_id)
                db.commit()
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
            candidates, skipped_sensitive_count = filter_sensitive_candidates(
                candidates=candidates,
                allow_sensitive=settings_state.sensitive_memory_enabled,
            )
            if not candidates:
                MemoryStore(db).rebuild_documents(user_id=conversation.user_id, conversation_id=conversation_id)
                db.commit()
                if skipped_sensitive_count:
                    logger.info(
                        "memory extraction skipped sensitive candidates | user_id=%s | conversation_id=%s | count=%s",
                        conversation.user_id,
                        conversation_id,
                        skipped_sensitive_count,
                    )
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
                resolved_candidate, status, confidence_state, expires_at, write_policy = resolved

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
                    confidence_state=confidence_state,
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

    def get_settings(self, *, db: Session, user_id: int):
        settings = MemorySettingsStore(db).get_or_create(user_id=user_id)
        db.commit()
        db.refresh(settings)
        return settings

    def update_settings(
        self,
        *,
        db: Session,
        user_id: int,
        saved_memories_enabled: bool | None = None,
        reference_chat_history_enabled: bool | None = None,
        memory_learning_enabled: bool | None = None,
        sensitive_memory_enabled: bool | None = None,
    ):
        settings = MemorySettingsStore(db).update(
            user_id=user_id,
            saved_memories_enabled=saved_memories_enabled,
            reference_chat_history_enabled=reference_chat_history_enabled,
            memory_learning_enabled=memory_learning_enabled,
            sensitive_memory_enabled=sensitive_memory_enabled,
        )
        db.commit()
        db.refresh(settings)
        return settings

    def clear_saved_memories(self, *, db: Session, user_id: int) -> int:
        deleted_count = MemorySettingsStore(db).clear_saved_memories(user_id=user_id)
        db.commit()
        return deleted_count

    def clear_chat_history_index(self, *, db: Session, user_id: int) -> int:
        deleted_count = MemorySettingsStore(db).clear_chat_history_index(user_id=user_id)
        db.commit()
        return deleted_count

    def list_pending_for_assistant_message(
        self,
        *,
        db: Session,
        user_id: int,
        assistant_message_id: int,
    ) -> list[MemoryItem]:
        return MemoryStore(db).list_pending_for_assistant_message(
            user_id=user_id,
            assistant_message_id=assistant_message_id,
        )

    def confirm_pending_memory(
        self,
        *,
        db: Session,
        memory: MemoryItem,
        user_id: int,
        scope: str | None = None,
        kind: str | None = None,
        title: str | None = None,
        detail: str | None = None,
        tags: list[str] | None = None,
    ) -> MemoryItem:
        updated = MemoryStore(db).confirm_pending_memory(
            memory,
            user_id=user_id,
            scope=scope,
            kind=kind,
            title=title,
            detail=detail,
            tags=tags,
        )
        db.commit()
        db.refresh(updated)
        return updated

    def reject_pending_memory(self, *, db: Session, memory: MemoryItem, user_id: int) -> MemoryItem:
        updated = MemoryStore(db).reject_pending_memory(memory, user_id=user_id)
        db.commit()
        db.refresh(updated)
        return updated

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

    def _settings_debug(self, settings_state: MemorySettingsState) -> dict[str, bool]:
        return {
            "saved_memories_enabled": settings_state.saved_memories_enabled,
            "reference_chat_history_enabled": settings_state.reference_chat_history_enabled,
            "memory_learning_enabled": settings_state.memory_learning_enabled,
            "sensitive_memory_enabled": settings_state.sensitive_memory_enabled,
        }

    def _build_query_hints(self, *, hit_items: list[MemoryItem], past_chat_refs) -> list[str]:
        hints: list[str] = []
        for item in sorted(hit_items, key=self._prompt_item_sort_key):
            text = " ".join([item.title or "", item.detail or ""]).strip()
            if text and text not in hints:
                hints.append(text[:180])
            if len(hints) >= 5:
                return hints
        for reference in past_chat_refs:
            text = (reference.summary or reference.excerpt or "").strip()
            if text and text not in hints:
                hints.append(text[:180])
            if len(hints) >= 5:
                return hints
        return hints
