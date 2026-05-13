from __future__ import annotations

import json

from sqlalchemy import and_, case, desc, func, literal, or_, select, text
from sqlalchemy.exc import DatabaseError

from ..storage.models import MemoryItem
from .store_utils import INJECTABLE_CONFIDENCE_STATES, MEMORY_STOPWORDS, TOKEN_PATTERN, memory_token_set, normalize_tags, utcnow
from .types import MemoryMatch


class MemoryRecallStoreMixin:
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
                # 中文注释：向量查询失败时继续执行关键词检索路径，保证记忆召回仍由明确的检索策略完成。

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
                MemoryItem.confidence_state.in_(tuple(INJECTABLE_CONFIDENCE_STATES)),
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
        touched_conversation_ids = {
            item.conversation_id
            for item in expired_items
            if item.conversation_id is not None
        }
        for item in expired_items:
            item.status = "archived"
            item.active = False
            item.updated_at = utcnow()
            self._db.add(item)
            self.reindex_memory(item)
        self._db.flush()
        for conversation_id in touched_conversation_ids:
            # 中文注释：working 记忆过期后，必须同步刷新会话摘要，避免模型继续看到已过期的临时上下文。
            self.rebuild_documents(user_id=user_id, conversation_id=conversation_id)

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
                    + CASE WHEN m.confidence_state = 'confirmed' THEN 24.0
                           WHEN m.confidence_state = 'inferred' THEN 8.0
                           ELSE 0.0 END
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
                  AND m.confidence_state IN ('inferred', 'confirmed')
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
                (MemoryItem.confidence_state == "confirmed", 24.0),
                (MemoryItem.confidence_state == "inferred", 8.0),
                else_=0.0,
            )
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
            if item.confidence_state == "confirmed":
                score += 24.0
            elif item.confidence_state == "inferred":
                score += 8.0
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
