from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from ..storage.models import MemoryItem
from .types import MemoryCandidate, MemoryMatch, MemoryScope

TOKEN_PATTERN = re.compile(r"[0-9A-Za-z_\u4e00-\u9fff]{2,}")
HAS_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
HAS_LATIN_PATTERN = re.compile(r"[A-Za-z]")
PURE_CJK_PATTERN = re.compile(r"^[\u4e00-\u9fff]+$")
TRANSIENT_MARKERS = (
    "当前",
    "这次",
    "本次",
    "这个项目",
    "该项目",
    "这个会话",
    "当前会话",
    "当前项目",
    "这轮",
    "暂时",
    "先",
    "接下来",
    "today",
    "current",
    "for this project",
    "for this chat",
    "this session",
)
MEMORY_STOPWORDS = {
    "user",
    "users",
    "name",
    "named",
    "called",
    "recognize",
    "recognized",
    "greeting",
    "profile",
    "preference",
    "goal",
    "project",
    "fact",
    "constraint",
    "personal",
    "assistant",
    "latest",
    "message",
    "reply",
    "detail",
    "details",
    "user's",
    "is",
    "are",
    "the",
    "a",
    "an",
    "用户",
    "名字",
    "姓名",
    "名称",
    "叫",
    "是",
    "偏好",
    "目标",
    "项目",
    "事实",
    "约束",
    "长期",
    "稳定",
}


@dataclass(frozen=True)
class MemoryCollection:
    global_items: list[MemoryItem]
    conversation_items: list[MemoryItem]


def normalize_tags(tags: list[str] | tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    for item in tags:
        value = str(item).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized


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
    jaccard = len(intersection) / len(union)
    overlap = len(intersection) / min(len(left_tokens), len(right_tokens))
    return max(jaccard, overlap)


class MemoryStore:
    def __init__(self, db: Session):
        self._db = db

    def list_collection(self, *, conversation_id: int | None) -> MemoryCollection:
        ordered = (
            desc(MemoryItem.pinned),
            desc(MemoryItem.last_used_at),
            desc(MemoryItem.updated_at),
            desc(MemoryItem.id),
        )
        global_items = self._db.scalars(
            select(MemoryItem)
            .where(MemoryItem.scope == "global")
            .order_by(*ordered)
        ).all()
        conversation_items: list[MemoryItem] = []
        if conversation_id is not None:
            conversation_items = self._db.scalars(
                select(MemoryItem)
                .where(
                    MemoryItem.scope == "conversation",
                    MemoryItem.conversation_id == conversation_id,
                )
                .order_by(*ordered)
            ).all()
        return MemoryCollection(global_items=global_items, conversation_items=conversation_items)

    def create_manual_memory(
        self,
        *,
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
            scope=scope,
            kind=kind,
            title=normalize_memory_text(title, max_length=255),
            detail=normalize_memory_text(detail, max_length=4000),
            tags_json=self.serialize_tags(tags),
            confidence=max(0.0, min(1.0, confidence)),
            pinned=bool(pinned),
            active=bool(active),
            conversation_id=conversation_id if scope == "conversation" else None,
        )
        self._db.add(memory)
        self._db.flush()
        self.reindex_memory(memory)
        return memory

    def update_manual_memory(
        self,
        memory: MemoryItem,
        *,
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
        memory.scope = scope
        memory.kind = kind
        memory.title = normalize_memory_text(title, max_length=255)
        memory.detail = normalize_memory_text(detail, max_length=4000)
        memory.tags_json = self.serialize_tags(tags)
        memory.confidence = max(0.0, min(1.0, confidence))
        memory.pinned = bool(pinned)
        memory.active = bool(active)
        memory.conversation_id = conversation_id if scope == "conversation" else None
        memory.updated_at = datetime.utcnow()
        self._db.add(memory)
        self._db.flush()
        self.reindex_memory(memory)
        return memory

    def delete_memory(self, memory: MemoryItem) -> None:
        self._delete_search_document(memory.id)
        self._db.delete(memory)
        self._db.flush()

    def merge_candidates(
        self,
        *,
        candidates: list[MemoryCandidate],
        conversation_id: int,
        user_message_id: int,
        assistant_message_id: int,
    ) -> list[MemoryItem]:
        if not candidates:
            return []

        scope_keys = {
            ("global", None),
            ("conversation", conversation_id),
        }
        existing_items = self._db.scalars(
            select(MemoryItem).where(
                (MemoryItem.scope == "global")
                | (
                    (MemoryItem.scope == "conversation")
                    & (MemoryItem.conversation_id == conversation_id)
                )
            )
        ).all()
        existing_by_key = {
            (item.scope, item.conversation_id, normalize_memory_key(item.title)): item
            for item in existing_items
            if (item.scope, item.conversation_id) in scope_keys
        }

        merged: list[MemoryItem] = []
        for candidate in candidates:
            title = normalize_memory_text(candidate.title, max_length=255)
            if not title:
                continue
            detail = normalize_memory_text(candidate.detail, max_length=4000)
            scope = self._resolved_scope(candidate)
            scoped_conversation_id = conversation_id if scope == "conversation" else None
            key = (scope, scoped_conversation_id, normalize_memory_key(title))
            existing = existing_by_key.get(key)
            if existing is None:
                existing = self._find_similar_existing(
                    candidate=candidate,
                    scope=scope,
                    detail=detail,
                    conversation_id=scoped_conversation_id,
                    existing_items=existing_items,
                )
            if existing is None:
                created = MemoryItem(
                    scope=scope,
                    kind=candidate.kind,
                    title=title,
                    detail=detail,
                    tags_json=self.serialize_tags(candidate.tags),
                    confidence=max(0.0, min(1.0, candidate.confidence)),
                    pinned=False,
                    active=True,
                    conversation_id=scoped_conversation_id,
                    source_user_message_id=user_message_id,
                    source_assistant_message_id=assistant_message_id,
                )
                self._db.add(created)
                self._db.flush()
                self.reindex_memory(created)
                existing_by_key[key] = created
                existing_items.append(created)
                merged.append(created)
                continue

            existing.kind = candidate.kind
            existing.detail = self._preferred_detail(current=existing.detail, incoming=detail)
            existing.tags_json = self.serialize_tags([*existing.tags, *candidate.tags])
            existing.confidence = max(existing.confidence, max(0.0, min(1.0, candidate.confidence)))
            existing.source_user_message_id = user_message_id
            existing.source_assistant_message_id = assistant_message_id
            existing.updated_at = datetime.utcnow()
            self._db.add(existing)
            self._db.flush()
            self.reindex_memory(existing)
            merged.append(existing)

        self._db.flush()
        return merged

    def recall(
        self,
        *,
        query: str,
        conversation_id: int,
        limit: int,
    ) -> list[MemoryMatch]:
        tokens = self._search_tokens(query)
        if not tokens:
            items = self._db.scalars(
                select(MemoryItem.id)
                .where(
                    MemoryItem.active.is_(True),
                    (MemoryItem.scope == "global")
                    | (
                        (MemoryItem.scope == "conversation")
                        & (MemoryItem.conversation_id == conversation_id)
                    ),
                )
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
        params = {
            "conversation_id": conversation_id,
            "match_query": match_query,
            "limit": limit,
        }
        rows = self._db.execute(
            text(
                """
                SELECT
                  m.id AS memory_id,
                  (
                    CASE WHEN m.pinned = 1 THEN 100.0 ELSE 0.0 END
                    + CASE WHEN m.scope = 'conversation' THEN 10.0 ELSE 0.0 END
                    - bm25(memory_search, 8.0, 2.0)
                  ) AS score
                FROM memory_search
                JOIN memory_items AS m ON m.id = memory_search.memory_id
                WHERE memory_search MATCH :match_query
                  AND m.active = 1
                  AND (
                    m.scope = 'global'
                    OR (m.scope = 'conversation' AND m.conversation_id = :conversation_id)
                  )
                ORDER BY score DESC, m.updated_at DESC, m.id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        return [
            MemoryMatch(
                memory_id=int(row["memory_id"]),
                score=float(row["score"] or 0.0),
            )
            for row in rows
        ]

    def touch(self, memory_ids: list[int]) -> None:
        if not memory_ids:
            return
        timestamp = datetime.utcnow()
        items = self._db.scalars(select(MemoryItem).where(MemoryItem.id.in_(memory_ids))).all()
        for item in items:
            item.last_used_at = timestamp
            self._db.add(item)
        self._db.flush()

    def get_by_id(self, memory_id: int) -> MemoryItem | None:
        return self._db.get(MemoryItem, memory_id)

    def list_pinned(
        self,
        *,
        conversation_id: int,
        limit: int,
    ) -> list[MemoryItem]:
        return self._db.scalars(
            select(MemoryItem)
            .where(
                MemoryItem.active.is_(True),
                MemoryItem.pinned.is_(True),
                (MemoryItem.scope == "global")
                | (
                    (MemoryItem.scope == "conversation")
                    & (MemoryItem.conversation_id == conversation_id)
                ),
            )
            .order_by(
                desc(MemoryItem.updated_at),
                desc(MemoryItem.id),
            )
            .limit(limit)
        ).all()

    def _search_tokens(self, value: str) -> list[str]:
        seen: list[str] = []
        for token in TOKEN_PATTERN.findall(value.casefold()):
            if token not in seen:
                seen.append(token)
        return seen[:8]

    def serialize_tags(self, tags: list[str] | tuple[str, ...]) -> str:
        normalized = normalize_tags(tags)
        return json.dumps(normalized, ensure_ascii=False)

    def _resolved_scope(self, candidate: MemoryCandidate) -> MemoryScope:
        if candidate.scope != "global":
            return candidate.scope
        if candidate.kind in {"goal", "project"}:
            return "conversation"
        combined = " ".join([candidate.title, candidate.detail]).casefold()
        if any(marker in combined for marker in TRANSIENT_MARKERS):
            return "conversation"
        return "global"

    def _find_similar_existing(
        self,
        *,
        candidate: MemoryCandidate,
        scope: MemoryScope,
        detail: str,
        conversation_id: int | None,
        existing_items: list[MemoryItem],
    ) -> MemoryItem | None:
        best_match: MemoryItem | None = None
        best_score = 0.0
        for item in existing_items:
            if item.scope != scope:
                continue
            if scope == "conversation" and item.conversation_id != conversation_id:
                continue
            if scope == "global" and item.conversation_id is not None:
                continue
            if item.kind != candidate.kind:
                continue
            score = memory_similarity(
                left_title=candidate.title,
                left_detail=detail,
                right_title=item.title,
                right_detail=item.detail,
            )
            if score > best_score:
                best_score = score
                best_match = item
        return best_match if best_score >= 0.72 else None

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
        parts = [memory.title, memory.detail, " ".join(memory.tags)]
        return " ".join(part.strip() for part in parts if part and part.strip())

    def _preferred_detail(self, *, current: str, incoming: str) -> str:
        if not incoming:
            return current
        if not current:
            return incoming
        if normalize_memory_key(current) == normalize_memory_key(incoming):
            return current

        current_has_cjk = bool(HAS_CJK_PATTERN.search(current))
        incoming_has_cjk = bool(HAS_CJK_PATTERN.search(incoming))
        current_has_latin = bool(HAS_LATIN_PATTERN.search(current))
        incoming_has_latin = bool(HAS_LATIN_PATTERN.search(incoming))
        if current_has_cjk and not incoming_has_cjk:
            return current
        if incoming_has_cjk and not current_has_cjk:
            return incoming
        if current_has_cjk and not current_has_latin and incoming_has_latin:
            return current
        if len(incoming) > len(current) * 1.35:
            return incoming
        return current
