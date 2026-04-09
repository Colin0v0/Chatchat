from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, desc, or_, select, text
from sqlalchemy.orm import Session

from ..storage.models import MemoryDocument, MemoryItem
from .normalizer import normalize_candidate
from .types import (
    MemoryCandidate,
    MemoryDocumentType,
    MemoryMatch,
    MemoryScope,
    MemoryWorkspaceCollection,
)

TOKEN_PATTERN = re.compile(r"[0-9A-Za-z_\u4e00-\u9fff]{2,}")
PURE_CJK_PATTERN = re.compile(r"^[\u4e00-\u9fff]+$")
MEMORY_STOPWORDS = {
    "the",
    "and",
    "user",
    "assistant",
    "memory",
    "context",
    "用户",
    "助手",
    "记忆",
    "上下文",
}

DOCUMENT_TITLES: dict[MemoryDocumentType, str] = {
    "user_profile": "User Profile",
    "workspace_profile": "Workspace Context",
    "conversation_brief": "Conversation Brief",
}

KIND_LABELS = {
    "profile": "Profile",
    "preference": "Preference",
    "goal": "Goal",
    "project": "Project",
    "fact": "Fact",
    "constraint": "Constraint",
}


@dataclass(frozen=True)
class MemoryCollection:
    global_items: list[MemoryItem]
    conversation_items: list[MemoryItem]


def utcnow() -> datetime:
    return datetime.utcnow()


def normalize_tags(tags: list[str] | tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    for item in tags:
        value = str(item).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized[:6]


def normalize_memory_text(value: str, *, max_length: int) -> str:
    compact = " ".join(value.strip().split())
    return compact[:max_length].strip()


def normalize_memory_key(value: str) -> str:
    return normalize_memory_text(value, max_length=255).casefold()


def memory_token_set(*parts: str) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        for token in TOKEN_PATTERN.findall(part.casefold()):
            normalized = token.strip()
            if len(normalized) < 2 or normalized in MEMORY_STOPWORDS:
                continue
            tokens.add(normalized)
            if PURE_CJK_PATTERN.fullmatch(normalized):
                tokens.update(_cjk_ngrams(normalized))
    return tokens


def _cjk_ngrams(value: str) -> set[str]:
    grams: set[str] = set()
    for size in (2, 3):
        if len(value) < size:
            continue
        for index in range(len(value) - size + 1):
            grams.add(value[index : index + size])
    return grams


def memory_similarity(
    *,
    left_title: str,
    left_detail: str,
    right_title: str,
    right_detail: str,
) -> float:
    left_text = normalize_memory_key(" ".join([left_title, left_detail]).strip())
    right_text = normalize_memory_key(" ".join([right_title, right_detail]).strip())
    if left_text and left_text == right_text:
        return 1.0

    left_tokens = memory_token_set(left_title, left_detail)
    right_tokens = memory_token_set(right_title, right_detail)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens & right_tokens
    if not intersection:
        return 0.0
    union = left_tokens | right_tokens
    return max(len(intersection) / len(union), len(intersection) / min(len(left_tokens), len(right_tokens)))


class MemoryStore:
    def __init__(self, db: Session):
        self._db = db

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
            candidate_global_items=tuple(self._list_items(user_id=user_id, scope="global", status="candidate")),
            candidate_conversation_items=tuple(
                self._list_items(
                    user_id=user_id,
                    scope="conversation",
                    status="candidate",
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
    ) -> MemoryItem:
        memory = MemoryItem(
            user_id=user_id,
            scope=scope,
            kind=kind,
            title=normalize_memory_text(title, max_length=255),
            detail=normalize_memory_text(detail, max_length=4000),
            tags_json=self.serialize_tags(tags),
            confidence=max(0.0, min(1.0, confidence)),
            status="active" if active else "archived",
            source_type="manual",
            modality="text",
            write_policy="manual",
            pinned=bool(pinned),
            active=bool(active),
            conversation_id=conversation_id if scope in {"conversation", "working"} else None,
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
                status="active" if scope == "global" else "candidate",
                source_type="auto",
                modality="text",
                write_policy="explicit" if scope == "global" else "auto_candidate",
                pinned=False,
                expires_at=None,
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
    ) -> MemoryItem:
        memory.user_id = user_id
        memory.scope = scope
        memory.kind = kind
        memory.title = normalize_memory_text(title, max_length=255)
        memory.detail = normalize_memory_text(detail, max_length=4000)
        memory.tags_json = self.serialize_tags(tags)
        memory.confidence = max(0.0, min(1.0, confidence))
        memory.status = "active" if active else "archived"
        memory.active = bool(active)
        memory.pinned = bool(pinned)
        memory.conversation_id = conversation_id if scope in {"conversation", "working"} else None
        memory.write_policy = "manual"
        memory.source_type = "manual"
        memory.last_confirmed_at = utcnow()
        memory.updated_at = utcnow()
        self._db.add(memory)
        self._db.flush()
        self.reindex_memory(memory)
        self.rebuild_documents(user_id=user_id, conversation_id=conversation_id)
        return memory

    def delete_memory(self, memory: MemoryItem) -> None:
        user_id = memory.user_id
        conversation_id = memory.conversation_id
        self._delete_search_document(memory.id)
        self._db.delete(memory)
        self._db.flush()
        if user_id is not None:
            self.rebuild_documents(user_id=user_id, conversation_id=conversation_id)

    def dismiss_candidate(self, memory: MemoryItem) -> MemoryItem:
        memory.status = "archived"
        memory.active = False
        memory.updated_at = utcnow()
        self._db.add(memory)
        self._db.flush()
        self.reindex_memory(memory)
        if memory.user_id is not None:
            self.rebuild_documents(user_id=memory.user_id, conversation_id=memory.conversation_id)
        return memory

    def promote_candidate(self, memory: MemoryItem, *, target_scope: MemoryScope | None = None) -> MemoryItem:
        next_scope = target_scope or memory.scope
        if next_scope == "working":
            next_scope = "conversation"
        memory.scope = next_scope
        memory.status = "active"
        memory.active = True
        memory.source_type = "promoted"
        memory.write_policy = "explicit"
        memory.last_confirmed_at = utcnow()
        memory.promoted_at = utcnow()
        memory.expires_at = None if next_scope != "working" else memory.expires_at
        memory.updated_at = utcnow()
        self._db.add(memory)
        self._db.flush()
        self.reindex_memory(memory)
        if memory.user_id is not None:
            self.rebuild_documents(user_id=memory.user_id, conversation_id=memory.conversation_id)
        return memory

    def upsert_auto_memory(
        self,
        *,
        candidate: MemoryCandidate,
        user_id: int,
        conversation_id: int,
        status: str,
        source_type: str,
        modality: str,
        write_policy: str,
        pinned: bool,
        expires_at: datetime | None,
        user_message_id: int,
        assistant_message_id: int,
    ) -> MemoryItem | None:
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
        if existing is None:
            existing = MemoryItem(
                user_id=user_id,
                scope=scope,
                kind=candidate.kind,
                title=title,
                detail=detail,
                tags_json=self.serialize_tags(candidate.tags),
                confidence=max(0.0, min(1.0, candidate.confidence)),
                status=status,
                source_type=source_type,
                modality=modality,
                write_policy=write_policy,
                pinned=pinned,
                active=status == "active",
                conversation_id=scoped_conversation_id,
                source_user_message_id=user_message_id,
                source_assistant_message_id=assistant_message_id,
                expires_at=expires_at,
                last_confirmed_at=utcnow() if status == "active" else None,
            )
            self._db.add(existing)
            self._db.flush()
            self.reindex_memory(existing)
            return existing

        existing.detail = self._preferred_detail(current=existing.detail, incoming=detail)
        existing.tags_json = self.serialize_tags([*existing.tags, *candidate.tags])
        existing.confidence = max(existing.confidence, max(0.0, min(1.0, candidate.confidence)))
        existing.status = status
        existing.active = status == "active"
        existing.source_type = source_type
        existing.modality = modality
        existing.write_policy = write_policy
        existing.expires_at = expires_at
        existing.source_user_message_id = user_message_id
        existing.source_assistant_message_id = assistant_message_id
        if status == "active":
            existing.last_confirmed_at = utcnow()
        existing.updated_at = utcnow()
        self._db.add(existing)
        self._db.flush()
        self.reindex_memory(existing)
        return existing

    def list_documents(self, *, user_id: int, conversation_id: int | None) -> list[MemoryDocument]:
        filters = [MemoryDocument.user_id == user_id]
        if conversation_id is not None:
            filters.append(
                or_(
                    MemoryDocument.conversation_id.is_(None),
                    MemoryDocument.conversation_id == conversation_id,
                )
            )
        else:
            filters.append(MemoryDocument.conversation_id.is_(None))
        return self._db.scalars(
            select(MemoryDocument)
            .where(*filters)
            .order_by(desc(MemoryDocument.updated_at), desc(MemoryDocument.id))
        ).all()

    def rebuild_documents(self, *, user_id: int, conversation_id: int | None) -> None:
        global_items = self._list_items(user_id=user_id, scope="global", status="active")
        conversation_items = self._list_items(
            user_id=user_id,
            scope="conversation",
            status="active",
            conversation_id=conversation_id,
        )
        working_items = self._list_items(
            user_id=user_id,
            scope="working",
            status="active",
            conversation_id=conversation_id,
        )

        profile_items = [item for item in global_items if item.kind in {"profile", "preference"}]
        workspace_items = [item for item in global_items if item.kind not in {"profile", "preference"}]
        conversation_doc_items = [*conversation_items, *working_items]

        self._upsert_document(
            user_id=user_id,
            conversation_id=None,
            doc_type="user_profile",
            items=profile_items,
        )
        self._upsert_document(
            user_id=user_id,
            conversation_id=None,
            doc_type="workspace_profile",
            items=workspace_items,
        )
        self._upsert_document(
            user_id=user_id,
            conversation_id=conversation_id,
            doc_type="conversation_brief",
            items=conversation_doc_items,
        )

    def recall(
        self,
        *,
        query: str,
        user_id: int,
        conversation_id: int,
        limit: int,
    ) -> list[MemoryMatch]:
        self.expire_stale_working_memory(user_id=user_id)
        tokens = self._search_tokens(query)
        if not tokens:
            items = self._db.scalars(
                select(MemoryItem.id)
                .where(*self._active_scope_filters(user_id=user_id, conversation_id=conversation_id))
                .order_by(
                    desc(MemoryItem.pinned),
                    desc(MemoryItem.last_used_at),
                    desc(MemoryItem.updated_at),
                    desc(MemoryItem.id),
                )
                .limit(limit)
            ).all()
            return [MemoryMatch(memory_id=item, score=0.0) for item in items]

        match_query = " OR ".join(tokens)
        rows = self._db.execute(
            text(
                """
                SELECT
                  m.id AS memory_id,
                  (
                    CASE WHEN m.pinned = 1 THEN 100.0 ELSE 0.0 END
                    + CASE WHEN m.scope = 'working' THEN 18.0
                           WHEN m.scope = 'conversation' THEN 9.0
                           ELSE 0.0 END
                    - bm25(memory_search, 8.0, 2.0)
                  ) AS score
                FROM memory_search
                JOIN memory_items AS m ON m.id = memory_search.memory_id
                WHERE memory_search MATCH :match_query
                  AND m.user_id = :user_id
                  AND m.status = 'active'
                  AND m.active = 1
                  AND (
                    m.scope = 'global'
                    OR (m.scope = 'conversation' AND m.conversation_id = :conversation_id)
                    OR (m.scope = 'working' AND m.conversation_id = :conversation_id)
                  )
                  AND (m.expires_at IS NULL OR m.expires_at > CURRENT_TIMESTAMP)
                ORDER BY score DESC, m.updated_at DESC, m.id DESC
                LIMIT :limit
                """
            ),
            {
                "match_query": match_query,
                "user_id": user_id,
                "conversation_id": conversation_id,
                "limit": limit,
            },
        ).mappings().all()
        return [MemoryMatch(memory_id=int(row["memory_id"]), score=float(row["score"] or 0.0)) for row in rows]

    def touch(self, memory_ids: list[int], *, user_id: int) -> None:
        if not memory_ids:
            return
        timestamp = utcnow()
        items = self._db.scalars(
            select(MemoryItem).where(
                MemoryItem.id.in_(memory_ids),
                MemoryItem.user_id == user_id,
            )
        ).all()
        for item in items:
            item.last_used_at = timestamp
            self._db.add(item)
        self._db.flush()

    def get_by_id(self, memory_id: int, *, user_id: int) -> MemoryItem | None:
        return self._db.scalar(
            select(MemoryItem).where(
                MemoryItem.id == memory_id,
                MemoryItem.user_id == user_id,
            )
        )

    def list_pinned(self, *, user_id: int, conversation_id: int, limit: int) -> list[MemoryItem]:
        self.expire_stale_working_memory(user_id=user_id)
        return self._db.scalars(
            select(MemoryItem)
            .where(
                MemoryItem.user_id == user_id,
                MemoryItem.status == "active",
                MemoryItem.active.is_(True),
                MemoryItem.pinned.is_(True),
                or_(
                    MemoryItem.scope == "global",
                    and_(MemoryItem.scope == "conversation", MemoryItem.conversation_id == conversation_id),
                    and_(MemoryItem.scope == "working", MemoryItem.conversation_id == conversation_id),
                ),
                or_(MemoryItem.expires_at.is_(None), MemoryItem.expires_at > utcnow()),
            )
            .order_by(desc(MemoryItem.updated_at), desc(MemoryItem.id))
            .limit(limit)
        ).all()

    def expire_stale_working_memory(self, *, user_id: int) -> None:
        expired_items = self._db.scalars(
            select(MemoryItem).where(
                MemoryItem.user_id == user_id,
                MemoryItem.scope == "working",
                MemoryItem.status == "active",
                MemoryItem.expires_at.is_not(None),
                MemoryItem.expires_at <= utcnow(),
            )
        ).all()
        if not expired_items:
            return
        for item in expired_items:
            item.status = "archived"
            item.active = False
            item.updated_at = utcnow()
            self._db.add(item)
            self.reindex_memory(item)
        self._db.flush()

    def serialize_tags(self, tags: list[str] | tuple[str, ...]) -> str:
        return json.dumps(normalize_tags(tags), ensure_ascii=False)

    def reindex_memory(self, memory: MemoryItem) -> None:
        self._delete_search_document(memory.id)
        self._db.execute(
            text(
                """
                INSERT INTO memory_search(rowid, memory_id, content)
                VALUES (:rowid, :memory_id, :content)
                """
            ),
            {
                "rowid": memory.id,
                "memory_id": memory.id,
                "content": self._search_content(memory),
            },
        )

    def _delete_search_document(self, memory_id: int) -> None:
        self._db.execute(
            text("DELETE FROM memory_search WHERE rowid = :rowid"),
            {"rowid": memory_id},
        )

    def _search_content(self, memory: MemoryItem) -> str:
        parts = [
            memory.scope,
            memory.status,
            memory.kind,
            memory.title,
            memory.detail,
            " ".join(memory.tags),
        ]
        return " ".join(part.strip() for part in parts if part and part.strip())

    def _search_tokens(self, value: str) -> list[str]:
        seen: list[str] = []
        for token in TOKEN_PATTERN.findall(value.casefold()):
            if token not in seen and token not in MEMORY_STOPWORDS:
                seen.append(token)
        return seen[:8]

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

    def _resolved_auto_scope(self, candidate: MemoryCandidate) -> MemoryScope:
        combined = " ".join([candidate.title, candidate.detail]).casefold()
        if candidate.scope == "global" and (
            candidate.kind in {"goal", "project"} or any(marker in combined for marker in ("当前", "这次", "本次", "先", "暂时"))
        ):
            return "conversation"
        return candidate.scope

    def _preferred_detail(self, *, current: str, incoming: str) -> str:
        if not incoming:
            return current
        if not current:
            return incoming
        if normalize_memory_key(current) == normalize_memory_key(incoming):
            return current
        return incoming if len(incoming) > len(current) else current

    def _upsert_document(
        self,
        *,
        user_id: int,
        conversation_id: int | None,
        doc_type: MemoryDocumentType,
        items: list[MemoryItem],
    ) -> None:
        existing = self._db.scalar(
            select(MemoryDocument).where(
                MemoryDocument.user_id == user_id,
                MemoryDocument.conversation_id == conversation_id,
                MemoryDocument.doc_type == doc_type,
            )
        )
        content = self._render_document(doc_type=doc_type, items=items)
        if not content:
            if existing is not None:
                self._db.delete(existing)
                self._db.flush()
            return

        source_ids = [item.id for item in items]
        if existing is None:
            existing = MemoryDocument(
                user_id=user_id,
                conversation_id=conversation_id,
                doc_type=doc_type,
                title=DOCUMENT_TITLES[doc_type],
                content=content,
                source_memory_ids_json=json.dumps(source_ids, ensure_ascii=False),
                auto_managed=True,
            )
            self._db.add(existing)
            self._db.flush()
            return

        existing.title = DOCUMENT_TITLES[doc_type]
        existing.content = content
        existing.source_memory_ids_json = json.dumps(source_ids, ensure_ascii=False)
        existing.auto_managed = True
        existing.updated_at = utcnow()
        self._db.add(existing)
        self._db.flush()

    def _render_document(self, *, doc_type: MemoryDocumentType, items: list[MemoryItem]) -> str:
        if not items:
            return ""

        ordered = sorted(items, key=lambda item: (not item.pinned, item.kind, -(item.id or 0)))
        groups: dict[str, list[MemoryItem]] = {}
        for item in ordered:
            groups.setdefault(item.kind, []).append(item)

        lines: list[str] = []
        if doc_type == "user_profile":
            lines.append("Stable user profile. Prefer direct evidence from the current conversation if conflicts appear.")
        elif doc_type == "workspace_profile":
            lines.append("Persistent workspace context shared across this user's conversations.")
        else:
            lines.append("Current thread brief. These points describe the ongoing conversation only.")

        for kind, group in groups.items():
            lines.append("")
            lines.append(f"{KIND_LABELS.get(kind, kind.title())}:")
            for item in group[:12]:
                line = f"- {item.title}"
                if item.detail:
                    line += f" :: {item.detail}"
                if item.scope == "working" and item.expires_at is not None:
                    line += f" [expires {item.expires_at.strftime('%Y-%m-%d %H:%M')}]"
                lines.append(line)
        return "\n".join(lines).strip()

    def _active_scope_filters(self, *, user_id: int, conversation_id: int):
        return [
            MemoryItem.user_id == user_id,
            MemoryItem.status == "active",
            MemoryItem.active.is_(True),
            or_(
                MemoryItem.scope == "global",
                and_(MemoryItem.scope == "conversation", MemoryItem.conversation_id == conversation_id),
                and_(MemoryItem.scope == "working", MemoryItem.conversation_id == conversation_id),
            ),
            or_(MemoryItem.expires_at.is_(None), MemoryItem.expires_at > utcnow()),
        ]
