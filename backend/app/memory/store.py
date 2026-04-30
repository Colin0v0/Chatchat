from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, desc, func, literal, or_, select, text
from sqlalchemy.exc import DatabaseError
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
    # 中文注释：统一返回带 UTC 时区的时间，避免和数据库里的 aware datetime 混用时报错。
    return datetime.now(timezone.utc)


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
        if embedding is not None:
            memory.embedding = embedding
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
        embedding: list[float] | None = None,
        action: str = "add",
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

        # Handle remove: archive the similar existing memory and do not create new.
        if action == "remove":
            if existing is not None:
                existing.status = "archived"
                existing.active = False
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
            existing.updated_at = utcnow()
            self._db.add(existing)
            self._db.flush()
            self.reindex_memory(existing)
            # Force creation of a new item by nulling existing.
            existing = None

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
                embedding=embedding if embedding else None,
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
        if embedding is not None:
            existing.embedding = embedding
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
        query_embedding: list[float] | None = None,
        vector_weight: float = 0.75,
        keyword_weight: float = 0.25,
    ) -> list[MemoryMatch]:
        self.expire_stale_working_memory(user_id=user_id)

        # Prefer vector search when embedding is available and we're on PostgreSQL.
        if (
            query_embedding
            and len(query_embedding) > 0
            and not self._uses_sqlite_memory_search()
        ):
            try:
                return self._recall_with_vector_search(
                    query_embedding=query_embedding,
                    query=query,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    limit=limit,
                    vector_weight=vector_weight,
                    keyword_weight=keyword_weight,
                )
            except DatabaseError:
                self._db.rollback()
                # fall through to keyword-only recall

        tokens = self._search_tokens(query)
        if not tokens:
            items = self._list_ranked_active_memory_ids(
                user_id=user_id,
                conversation_id=conversation_id,
                limit=limit,
            )
            return [MemoryMatch(memory_id=item, score=0.0) for item in items]

        if not self._uses_sqlite_memory_search():
            try:
                return self._recall_with_database_search(
                    tokens=tokens,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    limit=limit,
                )
            except DatabaseError:
                self._db.rollback()
                return self._recall_without_sqlite_fts(
                    tokens=tokens,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    limit=limit,
                )

        match_query = " OR ".join(tokens)
        try:
            rows = self._run_recall_query(
                match_query=match_query,
                user_id=user_id,
                conversation_id=conversation_id,
                limit=limit,
            )
        except DatabaseError as exc:
            if "database disk image is malformed" not in str(exc).lower():
                raise
            self._db.rollback()
            self._rebuild_search_index()
            rows = self._run_recall_query(
                match_query=match_query,
                user_id=user_id,
                conversation_id=conversation_id,
                limit=limit,
            )
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

    def set_memory_embedding(self, memory_id: int, embedding: list[float] | None) -> None:
        item = self._db.scalar(select(MemoryItem).where(MemoryItem.id == memory_id))
        if item is not None:
            item.embedding = embedding
            self._db.add(item)
            self._db.flush()

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
        if not self._uses_sqlite_memory_search():
            return
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
        if not self._uses_sqlite_memory_search():
            return
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

    def _run_recall_query(
        self,
        *,
        match_query: str,
        user_id: int,
        conversation_id: int,
        limit: int,
    ) -> list[dict[str, object]]:
        return self._db.execute(
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

    def _rebuild_search_index(self) -> None:
        if not self._uses_sqlite_memory_search():
            return
        self._db.execute(text("DROP TABLE IF EXISTS memory_search"))
        self._db.execute(
            text(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_search
                USING fts5(memory_id UNINDEXED, content, tokenize='unicode61')
                """
            )
        )
        self._db.execute(
            text(
                """
                INSERT INTO memory_search(rowid, memory_id, content)
                SELECT
                  id,
                  id,
                  coalesce(title, '') || ' ' || coalesce(detail, '') || ' ' || coalesce(tags_json, '')
                FROM memory_items
                """
            )
        )
        self._db.flush()

    def _list_ranked_active_memory_ids(
        self,
        *,
        user_id: int,
        conversation_id: int,
        limit: int,
    ) -> list[int]:
        return self._db.scalars(
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

    def _recall_with_vector_search(
        self,
        *,
        query_embedding: list[float],
        query: str,
        user_id: int,
        conversation_id: int,
        limit: int,
        vector_weight: float = 0.75,
        keyword_weight: float = 0.25,
    ) -> list[MemoryMatch]:
        candidate_limit = max(limit * 3, limit + 8)

        # 1. Vector recall via pgvector cosine_distance
        distance_expr = MemoryItem.embedding.cosine_distance(query_embedding)
        vector_rows = self._db.execute(
            select(MemoryItem.id, distance_expr.label("distance"))
            .where(
                *self._active_scope_filters(user_id=user_id, conversation_id=conversation_id),
                MemoryItem.embedding.is_not(None),
            )
            .order_by(distance_expr.asc(), MemoryItem.updated_at.desc(), MemoryItem.id.desc())
            .limit(candidate_limit)
        ).mappings().all()

        merged: dict[int, dict[str, float]] = {}
        vector_scores_list: list[float] = []
        for row in vector_rows:
            memory_id = int(row["id"])
            distance = float(row["distance"] or 1.0)
            vector_score = max(0.0, 1.0 - distance)
            merged[memory_id] = {"vector": vector_score, "keyword": 0.0}
            vector_scores_list.append(vector_score)

        # 2. Keyword recall as supplement (for items without embedding or weak vector match)
        tokens = self._search_tokens(query)
        keyword_scores_list: list[float] = []
        if tokens:
            keyword_matches = self._recall_with_database_search(
                tokens=tokens,
                user_id=user_id,
                conversation_id=conversation_id,
                limit=candidate_limit,
            )
            # Normalize keyword scores to [0, 1]
            raw_keyword_scores = [m.score for m in keyword_matches]
            min_k = min(raw_keyword_scores) if raw_keyword_scores else 0.0
            max_k = max(raw_keyword_scores) if raw_keyword_scores else 0.0
            for match in keyword_matches:
                item = merged.setdefault(match.memory_id, {"vector": 0.0, "keyword": 0.0})
                if max_k > min_k:
                    norm = (match.score - min_k) / (max_k - min_k)
                elif max_k > 0:
                    norm = 1.0
                else:
                    norm = 0.0
                item["keyword"] = max(item["keyword"], norm)
                keyword_scores_list.append(norm)

        # 3. Hybrid scoring
        if not merged:
            return []

        # Normalize vector scores to [0, 1]
        if vector_scores_list:
            min_v = min(vector_scores_list)
            max_v = max(vector_scores_list)
        else:
            min_v = max_v = 0.0

        scored_matches: list[MemoryMatch] = []
        for memory_id, scores in merged.items():
            v_score = scores["vector"]
            k_score = scores["keyword"]
            if max_v > min_v:
                v_norm = (v_score - min_v) / (max_v - min_v)
            elif max_v > 0:
                v_norm = 1.0
            else:
                v_norm = 0.0
            hybrid = vector_weight * v_norm + keyword_weight * k_score
            scored_matches.append(MemoryMatch(memory_id=memory_id, score=hybrid))

        scored_matches.sort(key=lambda m: (m.score, m.memory_id), reverse=True)
        return scored_matches[:limit]

    def _recall_with_database_search(
        self,
        *,
        tokens: list[str],
        user_id: int,
        conversation_id: int,
        limit: int,
    ) -> list[MemoryMatch]:
        lowered_title = func.lower(func.coalesce(MemoryItem.title, ""))
        lowered_detail = func.lower(func.coalesce(MemoryItem.detail, ""))
        lowered_tags = func.lower(func.coalesce(MemoryItem.tags_json, ""))
        lowered_scope = func.lower(func.coalesce(MemoryItem.scope, ""))
        lowered_kind = func.lower(func.coalesce(MemoryItem.kind, ""))

        score_expr = (
            case((MemoryItem.pinned.is_(True), 100.0), else_=0.0)
            + case(
                (MemoryItem.scope == "working", 18.0),
                (MemoryItem.scope == "conversation", 9.0),
                else_=0.0,
            )
        )
        token_filters = []
        for token in tokens:
            pattern = f"%{token.casefold()}%"
            title_match = lowered_title.like(pattern)
            detail_match = lowered_detail.like(pattern)
            tags_match = lowered_tags.like(pattern)
            scope_match = lowered_scope.like(pattern)
            kind_match = lowered_kind.like(pattern)
            token_filters.append(or_(title_match, detail_match, tags_match, scope_match, kind_match))
            score_expr = (
                score_expr
                + case((title_match, 8.0), else_=0.0)
                + case((detail_match, 4.0), else_=0.0)
                + case((tags_match, 3.0), else_=0.0)
                + case((scope_match, 2.0), else_=0.0)
                + case((kind_match, 1.5), else_=0.0)
            )

        rows = self._db.execute(
            select(
                MemoryItem.id.label("memory_id"),
                score_expr.label("score"),
            )
            .where(
                *self._active_scope_filters(user_id=user_id, conversation_id=conversation_id),
                or_(*token_filters),
            )
            .order_by(
                desc(literal(1) * score_expr),
                desc(MemoryItem.updated_at),
                desc(MemoryItem.id),
            )
            .limit(limit)
        ).mappings().all()
        return [MemoryMatch(memory_id=int(row["memory_id"]), score=float(row["score"] or 0.0)) for row in rows]

    def _recall_without_sqlite_fts(
        self,
        *,
        tokens: list[str],
        user_id: int,
        conversation_id: int,
        limit: int,
    ) -> list[MemoryMatch]:
        items = self._db.scalars(
            select(MemoryItem).where(*self._active_scope_filters(user_id=user_id, conversation_id=conversation_id))
        ).all()
        if not items:
            return []

        token_set = set(tokens)
        scored_matches: list[MemoryMatch] = []
        for item in items:
            item_tokens = memory_token_set(
                item.scope or "",
                item.kind or "",
                item.title or "",
                item.detail or "",
                " ".join(item.tags),
            )
            if not item_tokens:
                continue
            overlap = token_set & item_tokens
            if not overlap:
                continue

            score = float(len(overlap) * 12.0)
            if item.pinned:
                score += 100.0
            if item.scope == "working":
                score += 18.0
            elif item.scope == "conversation":
                score += 9.0
            if item.last_used_at is not None:
                score += 1.5
            if item.updated_at is not None:
                score += 0.5

            scored_matches.append(MemoryMatch(memory_id=item.id, score=score))

        scored_matches.sort(key=lambda item: (item.score, item.memory_id), reverse=True)
        return scored_matches[:limit]

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
