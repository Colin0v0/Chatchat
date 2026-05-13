from __future__ import annotations

from sqlalchemy import and_, case, desc, func, literal, or_, select
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from ..chat.token_budget import truncate_text_to_token_budget
from ..storage.models import ChatHistoryEntry, Conversation, Message
from .store_utils import TOKEN_PATTERN, memory_token_set, utcnow
from .types import PastChatReference


class ChatHistoryRecallStore:
    def __init__(self, db: Session):
        self._db = db

    @property
    def _dialect_name(self) -> str:
        bind = self._db.get_bind()
        return bind.dialect.name if bind is not None else ""

    def upsert_turn(
        self,
        *,
        user_id: int,
        conversation: Conversation,
        user_message: Message,
        assistant_message: Message,
        summary: str = "",
        embedding: list[float] | None = None,
    ) -> ChatHistoryEntry | None:
        excerpt = _build_turn_excerpt(
            conversation_title=conversation.title,
            user_message=user_message.content,
            assistant_message=assistant_message.content,
        )
        if not summary.strip() and not excerpt.strip():
            return None
        existing = self._db.scalar(
            select(ChatHistoryEntry).where(
                ChatHistoryEntry.assistant_message_id == assistant_message.id,
                ChatHistoryEntry.user_id == user_id,
            )
        )
        if existing is None:
            existing = ChatHistoryEntry(
                user_id=user_id,
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
            )
        existing.conversation_title = (conversation.title or "").strip()[:255]
        existing.user_text = _compact_history_text(user_message.content, token_limit=180)
        existing.assistant_text = _compact_history_text(assistant_message.content, token_limit=240)
        existing.summary = _compact_history_text(summary, token_limit=160)
        existing.embedding = embedding if embedding else None
        existing.active = True
        existing.updated_at = utcnow()
        self._db.add(existing)
        self._db.flush()
        return existing

    def deactivate_conversation(self, *, user_id: int, conversation_id: int) -> int:
        entries = self._db.scalars(
            select(ChatHistoryEntry).where(
                ChatHistoryEntry.user_id == user_id,
                ChatHistoryEntry.conversation_id == conversation_id,
                ChatHistoryEntry.active.is_(True),
            )
        ).all()
        for entry in entries:
            entry.active = False
            entry.updated_at = utcnow()
            self._db.add(entry)
        self._db.flush()
        return len(entries)

    def recall(
        self,
        *,
        user_id: int,
        conversation_id: int,
        query: str,
        limit: int,
        query_embedding: list[float] | None = None,
        vector_weight: float = 0.72,
        keyword_weight: float = 0.28,
    ) -> list[PastChatReference]:
        if user_id <= 0 or not query.strip():
            return []
        if query_embedding and self._dialect_name == "postgresql":
            try:
                return self._recall_with_vector(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    query=query,
                    query_embedding=query_embedding,
                    limit=limit,
                    vector_weight=vector_weight,
                    keyword_weight=keyword_weight,
                )
            except DatabaseError:
                self._db.rollback()

        return self._recall_with_keywords(
            user_id=user_id,
            conversation_id=conversation_id,
            query=query,
            limit=limit,
        )

    def touch(self, *, user_id: int, entry_ids: list[int]) -> None:
        if not entry_ids:
            return
        entries = self._db.scalars(
            select(ChatHistoryEntry).where(
                ChatHistoryEntry.user_id == user_id,
                ChatHistoryEntry.id.in_(entry_ids),
            )
        ).all()
        timestamp = utcnow()
        for entry in entries:
            entry.last_used_at = timestamp
            self._db.add(entry)
        self._db.flush()

    def _recall_with_vector(
        self,
        *,
        user_id: int,
        conversation_id: int,
        query: str,
        query_embedding: list[float],
        limit: int,
        vector_weight: float,
        keyword_weight: float,
    ) -> list[PastChatReference]:
        candidate_limit = max(limit * 3, limit + 8)
        distance_expr = ChatHistoryEntry.embedding.cosine_distance(query_embedding)
        rows = self._db.execute(
            select(ChatHistoryEntry, distance_expr.label("distance"))
            .where(
                *self._active_filters(user_id=user_id, conversation_id=conversation_id),
                ChatHistoryEntry.embedding.is_not(None),
            )
            .order_by(distance_expr.asc(), ChatHistoryEntry.updated_at.desc(), ChatHistoryEntry.id.desc())
            .limit(candidate_limit)
        ).all()

        vector_scores = {
            row.ChatHistoryEntry.id: max(0.0, 1.0 - float(row.distance or 1.0))
            for row in rows
        }
        keyword_refs = self._recall_with_keywords(
            user_id=user_id,
            conversation_id=conversation_id,
            query=query,
            limit=candidate_limit,
        )
        keyword_scores = {ref.id: ref.score for ref in keyword_refs}
        ids = set(vector_scores) | set(keyword_scores)
        if not ids:
            return []

        entries = {
            entry.id: entry
            for entry in self._db.scalars(
                select(ChatHistoryEntry).where(ChatHistoryEntry.id.in_(ids))
            ).all()
        }
        max_vector = max(vector_scores.values()) if vector_scores else 0.0
        max_keyword = max(keyword_scores.values()) if keyword_scores else 0.0
        scored: list[tuple[float, ChatHistoryEntry]] = []
        for entry_id in ids:
            entry = entries.get(entry_id)
            if entry is None:
                continue
            vector_score = vector_scores.get(entry_id, 0.0)
            keyword_score = keyword_scores.get(entry_id, 0.0)
            normalized_vector = vector_score / max_vector if max_vector > 0 else 0.0
            normalized_keyword = keyword_score / max_keyword if max_keyword > 0 else 0.0
            score = vector_weight * normalized_vector + keyword_weight * normalized_keyword
            scored.append((score, entry))
        scored.sort(key=lambda item: (item[0], item[1].updated_at, item[1].id), reverse=True)
        return [self._to_reference(entry, score=score) for score, entry in scored[:limit]]

    def _recall_with_keywords(
        self,
        *,
        user_id: int,
        conversation_id: int,
        query: str,
        limit: int,
    ) -> list[PastChatReference]:
        tokens = _history_search_tokens(query)
        if not tokens:
            entries = self._db.scalars(
                select(ChatHistoryEntry)
                .where(*self._active_filters(user_id=user_id, conversation_id=conversation_id))
                .order_by(desc(ChatHistoryEntry.last_used_at), desc(ChatHistoryEntry.updated_at), desc(ChatHistoryEntry.id))
                .limit(limit)
            ).all()
            return [self._to_reference(entry, score=0.0) for entry in entries]

        if self._dialect_name == "postgresql":
            lowered_title = func.lower(func.coalesce(ChatHistoryEntry.conversation_title, ""))
            lowered_user = func.lower(func.coalesce(ChatHistoryEntry.user_text, ""))
            lowered_assistant = func.lower(func.coalesce(ChatHistoryEntry.assistant_text, ""))
            lowered_summary = func.lower(func.coalesce(ChatHistoryEntry.summary, ""))
            score_expr = literal(0.0)
            token_filters = []
            for token in tokens:
                pattern = f"%{token.casefold()}%"
                title_match = lowered_title.like(pattern)
                user_match = lowered_user.like(pattern)
                assistant_match = lowered_assistant.like(pattern)
                summary_match = lowered_summary.like(pattern)
                token_filters.append(or_(title_match, user_match, assistant_match, summary_match))
                score_expr = (
                    score_expr
                    + case((title_match, 5.0), else_=0.0)
                    + case((user_match, 6.0), else_=0.0)
                    + case((assistant_match, 3.0), else_=0.0)
                    + case((summary_match, 8.0), else_=0.0)
                )
            rows = self._db.execute(
                select(ChatHistoryEntry, score_expr.label("score"))
                .where(
                    *self._active_filters(user_id=user_id, conversation_id=conversation_id),
                    or_(*token_filters),
                )
                .order_by(desc(score_expr), desc(ChatHistoryEntry.updated_at), desc(ChatHistoryEntry.id))
                .limit(limit)
            ).all()
            return [self._to_reference(row.ChatHistoryEntry, score=float(row.score or 0.0)) for row in rows]

        entries = self._db.scalars(
            select(ChatHistoryEntry).where(*self._active_filters(user_id=user_id, conversation_id=conversation_id))
        ).all()
        query_tokens = set(tokens)
        scored: list[tuple[float, ChatHistoryEntry]] = []
        for entry in entries:
            item_tokens = memory_token_set(
                entry.conversation_title or "",
                entry.user_text or "",
                entry.assistant_text or "",
                entry.summary or "",
            )
            overlap = query_tokens & item_tokens
            if not overlap:
                continue
            scored.append((float(len(overlap) * 10), entry))
        scored.sort(key=lambda item: (item[0], item[1].updated_at, item[1].id), reverse=True)
        return [self._to_reference(entry, score=score) for score, entry in scored[:limit]]

    def _active_filters(self, *, user_id: int, conversation_id: int):
        return [
            ChatHistoryEntry.user_id == user_id,
            ChatHistoryEntry.active.is_(True),
            ChatHistoryEntry.conversation_id != conversation_id,
            or_(
                ChatHistoryEntry.summary != "",
                ChatHistoryEntry.user_text != "",
                ChatHistoryEntry.assistant_text != "",
            ),
        ]

    def _to_reference(self, entry: ChatHistoryEntry, *, score: float) -> PastChatReference:
        excerpt = entry.summary.strip()
        if not excerpt:
            excerpt = entry.user_text.strip()
        if not excerpt:
            excerpt = entry.assistant_text.strip()
        return PastChatReference(
            id=entry.id,
            conversation_id=entry.conversation_id,
            conversation_title=entry.conversation_title or "Untitled",
            user_message_id=entry.user_message_id,
            assistant_message_id=entry.assistant_message_id,
            summary=entry.summary or "",
            excerpt=_compact_history_text(excerpt, token_limit=80),
            score=score,
            updated_at=entry.updated_at or entry.created_at,
        )


def _history_search_tokens(value: str) -> list[str]:
    seen: list[str] = []
    for token in memory_token_set(value):
        if len(token) < 2 or token in seen:
            continue
        seen.append(token)
    return seen[:10]


def _compact_history_text(value: str, *, token_limit: int) -> str:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return ""
    return truncate_text_to_token_budget(normalized, token_budget=max(32, token_limit))


def _build_turn_excerpt(*, conversation_title: str, user_message: str, assistant_message: str) -> str:
    parts = [
        (conversation_title or "").strip(),
        (user_message or "").strip(),
        (assistant_message or "").strip(),
    ]
    return " ".join(part for part in parts if part)
