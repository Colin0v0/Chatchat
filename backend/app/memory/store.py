from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.orm import Session

from ..storage.models import MemoryItem
from .document_store import MemoryDocumentStoreMixin
from .normalizer import normalize_candidate
from .pending_store import PendingMemoryStoreMixin
from .recall_store import MemoryRecallStoreMixin
from .store_utils import (
    CONFLICT_SUBJECT_MARKERS,
    DETAILED_STYLE_MARKERS,
    INJECTABLE_CONFIDENCE_STATES,
    PROMOTE_EVIDENCE_THRESHOLD,
    PROMOTABLE_KINDS,
    SHORT_STYLE_MARKERS,
    MemoryCollection,
    memory_token_set,
    memory_similarity,
    normalize_memory_key,
    normalize_memory_text,
    serialize_evidence,
    utcnow,
)
from .types import (
    MemoryCandidate,
    MemoryScope,
    MemoryWorkspaceCollection,
)


class MemoryStore(PendingMemoryStoreMixin, MemoryDocumentStoreMixin, MemoryRecallStoreMixin):
    def __init__(self, db: Session):
        self._db = db

    @property
    def _dialect_name(self) -> str:
        bind = self._db.get_bind()
        return bind.dialect.name if bind is not None else ""

    def _uses_sqlite_memory_search(self) -> bool:
        return self._dialect_name == "sqlite"

    def list_collection(self, *, user_id: int, conversation_id: int | None) -> MemoryCollection:
        workspace = self.list_workspace(user_id=user_id, conversation_id=conversation_id)
        return MemoryCollection(
            global_items=list(workspace.active_global_items),
            conversation_items=list(workspace.active_conversation_items),
        )

    def list_workspace(self, *, user_id: int, conversation_id: int | None) -> MemoryWorkspaceCollection:
        self.expire_stale_working_memory(user_id=user_id)
        return MemoryWorkspaceCollection(
            documents=tuple(self.list_documents(user_id=user_id, conversation_id=conversation_id)),
            active_global_items=tuple(self._list_items(user_id=user_id, scope="global", status="active")),
            active_conversation_items=tuple(
                self._list_items(
                    user_id=user_id,
                    scope="conversation",
                    status="active",
                    conversation_id=conversation_id,
                )
            ),
            active_working_items=tuple(
                self._list_items(
                    user_id=user_id,
                    scope="working",
                    status="active",
                    conversation_id=conversation_id,
                )
            ),
        )

    def create_manual_memory(
        self,
        *,
        user_id: int,
        scope: MemoryScope,
        kind: str,
        title: str,
        detail: str,
        tags: list[str],
        confidence: float,
        pinned: bool,
        active: bool,
        conversation_id: int | None,
        embedding: list[float] | None = None,
    ) -> MemoryItem:
        memory = MemoryItem(
            user_id=user_id,
            scope=scope,
            kind=kind,
            title=normalize_memory_text(title, max_length=255),
            detail=normalize_memory_text(detail, max_length=4000),
            tags_json=self.serialize_tags(tags),
            confidence=max(0.0, min(1.0, confidence)),
            confidence_state="confirmed",
            evidence_count=1,
            evidence_json=serialize_evidence(user_message_id=None, assistant_message_id=None),
            status="active" if active else "archived",
            source_type="manual",
            modality="text",
            write_policy="manual",
            pinned=bool(pinned),
            active=bool(active),
            conversation_id=conversation_id if scope in {"conversation", "working"} else None,
            embedding=embedding if embedding else None,
            last_confirmed_at=utcnow(),
        )
        self._db.add(memory)
        self._db.flush()
        self.reindex_memory(memory)
        self.rebuild_documents(user_id=user_id, conversation_id=conversation_id)
        return memory

    def merge_candidates(
        self,
        *,
        candidates: list[MemoryCandidate],
        user_id: int,
        conversation_id: int,
        user_message_id: int,
        assistant_message_id: int,
    ) -> list[MemoryItem]:
        merged: list[MemoryItem] = []
        for candidate in candidates:
            normalized_candidate = normalize_candidate(candidate)
            if normalized_candidate is None:
                continue
            scope = self._resolved_auto_scope(normalized_candidate)
            expires_at = utcnow() + timedelta(days=2) if scope == "working" else None
            write_policy = "session" if scope == "working" else "explicit"
            normalized_candidate = MemoryCandidate(
                scope=scope,
                kind=normalized_candidate.kind,
                title=normalized_candidate.title,
                detail=normalized_candidate.detail,
                tags=tuple([*normalized_candidate.tags, *candidate.tags]),
                confidence=normalized_candidate.confidence,
            )
            item = self.upsert_auto_memory(
                candidate=normalized_candidate,
                user_id=user_id,
                conversation_id=conversation_id,
                status="active",
                confidence_state="inferred",
                source_type="auto",
                modality="text",
                write_policy=write_policy,
                pinned=False,
                expires_at=expires_at,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
            )
            if item is not None:
                merged.append(item)
        self.rebuild_documents(user_id=user_id, conversation_id=conversation_id)
        return merged

    def update_manual_memory(
        self,
        memory: MemoryItem,
        *,
        user_id: int,
        scope: MemoryScope,
        kind: str,
        title: str,
        detail: str,
        tags: list[str],
        confidence: float,
        pinned: bool,
        active: bool,
        conversation_id: int | None,
        embedding: list[float] | None = None,
    ) -> MemoryItem:
        previous_user_id = memory.user_id
        previous_conversation_id = memory.conversation_id
        memory.user_id = user_id
        memory.scope = scope
        memory.kind = kind
        memory.title = normalize_memory_text(title, max_length=255)
        memory.detail = normalize_memory_text(detail, max_length=4000)
        memory.tags_json = self.serialize_tags(tags)
        memory.confidence = max(0.0, min(1.0, confidence))
        memory.confidence_state = "confirmed"
        memory.evidence_count = max(1, int(memory.evidence_count or 1))
        memory.status = "active" if active else "archived"
        memory.active = bool(active)
        memory.pinned = bool(pinned)
        memory.conversation_id = conversation_id if scope in {"conversation", "working"} else None
        memory.write_policy = "manual"
        memory.source_type = "manual"
        memory.last_confirmed_at = utcnow()
        memory.updated_at = utcnow()
        if embedding is not None:
            memory.embedding = embedding
        self._db.add(memory)
        self._db.flush()
        self.reindex_memory(memory)
        next_conversation_id = memory.conversation_id
        touched_pairs = {(user_id, next_conversation_id)}
        if previous_user_id is not None:
            # 中文注释：记忆从旧会话迁走时，旧会话的 conversation_brief 也要重建，否则 prompt 会继续注入旧内容。
            touched_pairs.add((previous_user_id, previous_conversation_id))
        for touched_user_id, touched_conversation_id in touched_pairs:
            self.rebuild_documents(user_id=touched_user_id, conversation_id=touched_conversation_id)
        return memory

    def delete_memory(self, memory: MemoryItem) -> None:
        user_id = memory.user_id
        conversation_id = memory.conversation_id
        self._delete_search_document(memory.id)
        self._db.delete(memory)
        self._db.flush()
        if user_id is not None:
            self.rebuild_documents(user_id=user_id, conversation_id=conversation_id)

    def upsert_auto_memory(
        self,
        *,
        candidate: MemoryCandidate,
        user_id: int,
        conversation_id: int,
        status: str,
        confidence_state: str,
        source_type: str,
        modality: str,
        write_policy: str,
        pinned: bool,
        expires_at: datetime | None,
        user_message_id: int,
        assistant_message_id: int,
        embedding: list[float] | None = None,
        action: str = "add",
    ) -> MemoryItem | None:
        if action == "add" and candidate.action != "add":
            action = candidate.action
        title = normalize_memory_text(candidate.title, max_length=255)
        if not title:
            return None
        detail = normalize_memory_text(candidate.detail, max_length=4000)
        scope = candidate.scope
        scoped_conversation_id = conversation_id if scope in {"conversation", "working"} else None
        existing = self._find_existing_item(
            user_id=user_id,
            scope=scope,
            status=status,
            kind=candidate.kind,
            title=title,
            detail=detail,
            conversation_id=scoped_conversation_id,
        )
        if existing is None and self._can_reuse_cross_scope_memory(candidate=candidate, confidence_state=confidence_state):
            existing = self._find_existing_cross_scope_item(
                user_id=user_id,
                kind=candidate.kind,
                title=title,
                detail=detail,
            )

        # Handle remove: archive the similar existing memory and do not create new.
        if action == "remove":
            if existing is not None:
                existing.status = "archived"
                existing.active = False
                existing.confidence_state = "rejected"
                existing.updated_at = utcnow()
                self._db.add(existing)
                self._db.flush()
                self.reindex_memory(existing)
                return existing
            return None

        # Handle replace: archive the old one, then create/update as new.
        if action == "replace" and existing is not None:
            existing.status = "archived"
            existing.active = False
            existing.confidence_state = "rejected"
            existing.updated_at = utcnow()
            self._db.add(existing)
            self._db.flush()
            self.reindex_memory(existing)
            # Force creation of a new item by nulling existing.
            existing = None

        if action == "replace" or self._has_contradiction_subject(title=title, detail=detail):
            self._archive_conflicting_items(
                user_id=user_id,
                scope=scope,
                kind=candidate.kind,
                title=title,
                detail=detail,
                conversation_id=scoped_conversation_id,
                exclude_id=existing.id if existing is not None else None,
            )

        if existing is None:
            resolved_state = self._normalized_confidence_state(confidence_state)
            existing = MemoryItem(
                user_id=user_id,
                scope=scope,
                kind=candidate.kind,
                title=title,
                detail=detail,
                tags_json=self.serialize_tags(candidate.tags),
                confidence=max(0.0, min(1.0, candidate.confidence)),
                confidence_state=resolved_state,
                evidence_count=1,
                evidence_json=serialize_evidence(
                    user_message_id=user_message_id,
                    assistant_message_id=assistant_message_id,
                ),
                status=status,
                source_type=source_type,
                modality=modality,
                write_policy=write_policy,
                pinned=pinned,
                active=status == "active",
                conversation_id=scoped_conversation_id,
                source_user_message_id=user_message_id,
                source_assistant_message_id=assistant_message_id,
                embedding=embedding if embedding else None,
                expires_at=expires_at,
                last_confirmed_at=utcnow() if resolved_state == "confirmed" and status == "active" else None,
            )
            self._db.add(existing)
            self._db.flush()
            self.reindex_memory(existing)
            return existing

        previous_scope = existing.scope
        previous_conversation_id = existing.conversation_id
        existing.detail = self._preferred_detail(current=existing.detail, incoming=detail)
        existing.tags_json = self.serialize_tags([*existing.tags, *candidate.tags])
        existing.confidence = max(existing.confidence, max(0.0, min(1.0, candidate.confidence)))
        existing.status = status
        existing.active = status == "active"
        existing.source_type = source_type
        existing.modality = modality
        existing.evidence_count = max(1, int(existing.evidence_count or 0)) + 1
        existing.evidence_json = serialize_evidence(
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            existing=existing.evidence,
        )
        next_state = self._merge_confidence_state(
            current=existing.confidence_state,
            incoming=confidence_state,
            evidence_count=existing.evidence_count,
            candidate=candidate,
        )
        if self._should_promote_to_global(candidate=candidate, evidence_count=existing.evidence_count):
            existing.scope = "global"
            existing.conversation_id = None
            existing.promoted_at = existing.promoted_at or utcnow()
            next_state = "confirmed"
            write_policy = "explicit"
        else:
            existing.scope = scope if existing.scope not in {"global"} else existing.scope
            existing.conversation_id = existing.conversation_id if existing.scope == "global" else scoped_conversation_id
        existing.confidence_state = next_state
        existing.write_policy = "explicit" if next_state == "confirmed" else write_policy
        existing.expires_at = expires_at
        existing.source_user_message_id = user_message_id
        existing.source_assistant_message_id = assistant_message_id
        if embedding is not None:
            existing.embedding = embedding
        if status == "active" and existing.confidence_state == "confirmed":
            existing.last_confirmed_at = utcnow()
        existing.updated_at = utcnow()
        self._db.add(existing)
        self._db.flush()
        self.reindex_memory(existing)
        if (previous_scope, previous_conversation_id) != (existing.scope, existing.conversation_id):
            # 中文注释：记忆晋升到全局后，原会话摘要也要刷新，防止同一条记忆在旧 conversation_brief 里重复出现。
            self.rebuild_documents(user_id=user_id, conversation_id=previous_conversation_id)
        return existing

    def _list_items(
        self,
        *,
        user_id: int,
        scope: MemoryScope,
        status: str,
        conversation_id: int | None = None,
    ) -> list[MemoryItem]:
        filters = [
            MemoryItem.user_id == user_id,
            MemoryItem.scope == scope,
            MemoryItem.status == status,
            MemoryItem.active.is_(status == "active"),
        ]
        if status == "active":
            filters.append(MemoryItem.confidence_state.in_(tuple(INJECTABLE_CONFIDENCE_STATES)))
        if scope in {"conversation", "working"}:
            if conversation_id is None:
                return []
            filters.append(MemoryItem.conversation_id == conversation_id)
        else:
            filters.append(MemoryItem.conversation_id.is_(None))
        filters.append(or_(MemoryItem.expires_at.is_(None), MemoryItem.expires_at > utcnow()))
        return self._db.scalars(
            select(MemoryItem)
            .where(*filters)
            .order_by(
                desc(MemoryItem.pinned),
                desc(MemoryItem.updated_at),
                desc(MemoryItem.id),
            )
        ).all()

    def _find_existing_item(
        self,
        *,
        user_id: int,
        scope: MemoryScope,
        status: str,
        kind: str,
        title: str,
        detail: str,
        conversation_id: int | None,
    ) -> MemoryItem | None:
        existing_items = self._db.scalars(
            select(MemoryItem).where(
                MemoryItem.user_id == user_id,
                MemoryItem.scope == scope,
                MemoryItem.status == status,
                MemoryItem.kind == kind,
                MemoryItem.conversation_id == conversation_id,
            )
        ).all()
        direct_key = normalize_memory_key(title)
        for item in existing_items:
            if normalize_memory_key(item.title) == direct_key:
                return item
        best_match: MemoryItem | None = None
        best_score = 0.0
        for item in existing_items:
            score = memory_similarity(
                left_title=title,
                left_detail=detail,
                right_title=item.title,
                right_detail=item.detail,
            )
            if score > best_score:
                best_score = score
                best_match = item
        return best_match if best_score >= 0.76 else None

    def _find_existing_cross_scope_item(
        self,
        *,
        user_id: int,
        kind: str,
        title: str,
        detail: str,
    ) -> MemoryItem | None:
        existing_items = self._db.scalars(
            select(MemoryItem).where(
                MemoryItem.user_id == user_id,
                MemoryItem.status == "active",
                MemoryItem.active.is_(True),
                MemoryItem.kind == kind,
                MemoryItem.confidence_state.in_(("inferred", "confirmed")),
            )
        ).all()
        best_match: MemoryItem | None = None
        best_score = 0.0
        for item in existing_items:
            score = memory_similarity(
                left_title=title,
                left_detail=detail,
                right_title=item.title,
                right_detail=item.detail,
            )
            if score > best_score:
                best_score = score
                best_match = item
        return best_match if best_score >= 0.76 else None

    def _can_reuse_cross_scope_memory(self, *, candidate: MemoryCandidate, confidence_state: str) -> bool:
        return confidence_state in {"inferred", "confirmed"} and candidate.kind in PROMOTABLE_KINDS

    def _normalized_confidence_state(self, value: str) -> str:
        return value if value in {"pending", "inferred", "confirmed", "rejected"} else "inferred"

    def _merge_confidence_state(
        self,
        *,
        current: str,
        incoming: str,
        evidence_count: int,
        candidate: MemoryCandidate,
    ) -> str:
        incoming_state = self._normalized_confidence_state(incoming)
        if incoming_state in {"confirmed", "rejected"}:
            return incoming_state
        if current == "confirmed":
            return "confirmed"
        if self._should_promote_to_global(candidate=candidate, evidence_count=evidence_count):
            return "confirmed"
        if current == "pending" and incoming_state == "inferred":
            return "inferred"
        return incoming_state if incoming_state != "pending" else current

    def _should_promote_to_global(self, *, candidate: MemoryCandidate, evidence_count: int) -> bool:
        return candidate.kind in PROMOTABLE_KINDS and evidence_count >= PROMOTE_EVIDENCE_THRESHOLD

    def _has_contradiction_subject(self, *, title: str, detail: str) -> bool:
        text = " ".join([title, detail]).casefold()
        return bool(
            self._contains_any(text, SHORT_STYLE_MARKERS)
            or self._contains_any(text, DETAILED_STYLE_MARKERS)
            or self._contains_any(text, CONFLICT_SUBJECT_MARKERS)
        )

    def _archive_conflicting_items(
        self,
        *,
        user_id: int,
        scope: str,
        kind: str,
        title: str,
        detail: str,
        conversation_id: int | None,
        exclude_id: int | None = None,
    ) -> None:
        incoming_text = " ".join([title, detail]).casefold()
        if not self._has_contradiction_subject(title=title, detail=detail):
            return
        filters = [
            MemoryItem.user_id == user_id,
            MemoryItem.status == "active",
            MemoryItem.active.is_(True),
            MemoryItem.kind == kind,
            MemoryItem.confidence_state.in_(("pending", "inferred", "confirmed")),
        ]
        if scope == "global":
            filters.append(MemoryItem.scope == "global")
        elif conversation_id is not None:
            filters.append(
                or_(
                    MemoryItem.scope == "global",
                    and_(MemoryItem.scope == scope, MemoryItem.conversation_id == conversation_id),
                )
            )
        else:
            filters.append(MemoryItem.scope == scope)
        existing_items = self._db.scalars(select(MemoryItem).where(*filters)).all()
        for item in existing_items:
            if exclude_id is not None and item.id == exclude_id:
                continue
            existing_text = " ".join([item.title or "", item.detail or ""]).casefold()
            if not self._memories_conflict(incoming_text, existing_text):
                continue
            item.status = "archived"
            item.active = False
            item.confidence_state = "rejected"
            item.updated_at = utcnow()
            self._db.add(item)
            self.reindex_memory(item)
        self._db.flush()

    def _style_preferences_conflict(self, left: str, right: str) -> bool:
        left_short = self._contains_any(left, SHORT_STYLE_MARKERS)
        left_detailed = self._contains_any(left, DETAILED_STYLE_MARKERS)
        right_short = self._contains_any(right, SHORT_STYLE_MARKERS)
        right_detailed = self._contains_any(right, DETAILED_STYLE_MARKERS)
        return (left_short and right_detailed) or (left_detailed and right_short)

    def _memories_conflict(self, left: str, right: str) -> bool:
        if self._style_preferences_conflict(left, right):
            return True
        shared_subjects = {
            marker
            for marker in CONFLICT_SUBJECT_MARKERS
            if marker in left and marker in right
        }
        if not shared_subjects:
            return False
        left_tokens = memory_token_set(left)
        right_tokens = memory_token_set(right)
        if not left_tokens or not right_tokens:
            return False
        overlap = left_tokens & right_tokens
        # 中文注释：同一主体但实体值明显不同，视为新事实覆盖旧事实。
        return len(overlap) < min(len(left_tokens), len(right_tokens)) * 0.65

    def _contains_any(self, text: str, markers: set[str]) -> bool:
        return any(marker in text for marker in markers)

    def _resolved_auto_scope(self, candidate: MemoryCandidate) -> MemoryScope:
        combined = " ".join([candidate.title, candidate.detail]).casefold()
        # 中文注释：自动提取出的短期目标、项目和临时约束统一落到 working，避免混入长期记忆。
        if candidate.kind in {"goal", "project", "constraint"} or any(
            marker in combined for marker in ("当前", "这次", "本次", "先", "暂时")
        ):
            return "working"
        return candidate.scope

    def _preferred_detail(self, *, current: str, incoming: str) -> str:
        if not incoming:
            return current
        if not current:
            return incoming
        if normalize_memory_key(current) == normalize_memory_key(incoming):
            return current
        # Prefer the latest information over the longest text.
        # This ensures corrections (e.g., "my name is actually X") take effect.
        return incoming

    def _active_scope_filters(self, *, user_id: int, conversation_id: int):
        return [
            MemoryItem.user_id == user_id,
            MemoryItem.status == "active",
            MemoryItem.active.is_(True),
            MemoryItem.confidence_state.in_(tuple(INJECTABLE_CONFIDENCE_STATES)),
            or_(
                MemoryItem.scope == "global",
                and_(MemoryItem.scope == "conversation", MemoryItem.conversation_id == conversation_id),
                and_(MemoryItem.scope == "working", MemoryItem.conversation_id == conversation_id),
            ),
            or_(MemoryItem.expires_at.is_(None), MemoryItem.expires_at > utcnow()),
        ]
