import unittest
from datetime import timedelta

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.memory.history_store import ChatHistoryRecallStore
from app.memory.settings_store import MemorySettingsStore
from app.memory.store import MemoryStore, utcnow
from app.memory.types import MemoryCandidate
from app.storage.database import Base
from app.storage.models import ChatHistoryEntry, Conversation, MemoryDocument, MemoryItem, Message, User


class _ArrayLikeEmbedding:
    def __init__(self, *, value: float = 0.125, length: int = 1024):
        self._values = [value] * length

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __bool__(self):
        raise ValueError("The truth value of an array with more than one element is ambiguous. Use a.any() or a.all()")


class MemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE VIRTUAL TABLE memory_search
                    USING fts5(memory_id UNINDEXED, content, tokenize='unicode61')
                    """
                )
            )
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db: Session = self.session_factory()
        self.store = MemoryStore(self.db)
        self.user = User(username="tester", password_hash="hash", is_active=True)
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_merge_candidates_collapses_similar_global_memory(self):
        existing = self.store.create_manual_memory(
            user_id=self.user.id,
            scope="global",
            kind="profile",
            title="姓名",
            detail="用户叫杜宇",
            tags=["个人"],
            confidence=0.9,
            pinned=False,
            active=True,
            conversation_id=None,
        )
        self.db.commit()

        merged = self.store.merge_candidates(
            candidates=[
                MemoryCandidate(
                    scope="global",
                    kind="profile",
                    title="User Name",
                    detail="User's name is 杜宇",
                    tags=("personal",),
                    confidence=1.0,
                )
            ],
            user_id=self.user.id,
            conversation_id=12,
            user_message_id=101,
            assistant_message_id=102,
        )
        self.db.commit()

        items = self.db.scalars(select(MemoryItem)).all()
        self.assertEqual(len(items), 1)
        self.assertEqual(merged[0].id, existing.id)
        self.assertEqual(items[0].title, "姓名")
        self.assertEqual(items[0].detail, "用户叫杜宇")
        self.assertIn("personal", items[0].tags)

    def test_memory_embedding_accepts_array_like_values_without_boolean_coercion(self):
        memory = self.store.create_manual_memory(
            user_id=self.user.id,
            scope="global",
            kind="fact",
            title="数组向量",
            detail="embedding 可能来自 numpy 或 pgvector",
            tags=[],
            confidence=0.9,
            pinned=False,
            active=True,
            conversation_id=None,
            embedding=_ArrayLikeEmbedding(),  # type: ignore[arg-type]
        )
        self.db.commit()

        self.assertIsNotNone(memory.embedding)
        assert memory.embedding is not None
        self.assertEqual(len(memory.embedding), 1024)
        self.assertEqual(memory.embedding[0], 0.125)

        updated = self.store.upsert_auto_memory(
            candidate=MemoryCandidate(
                scope="global",
                kind="fact",
                title="数组向量自动记忆",
                detail="自动记忆写入也不能布尔判断 embedding",
                tags=(),
                confidence=0.9,
            ),
            user_id=self.user.id,
            conversation_id=12,
            status="active",
            confidence_state="inferred",
            source_type="auto",
            modality="text",
            write_policy="explicit",
            pinned=False,
            expires_at=None,
            user_message_id=101,
            assistant_message_id=102,
            embedding=_ArrayLikeEmbedding(value=0.25),  # type: ignore[arg-type]
        )
        self.db.commit()

        self.assertIsNotNone(updated)
        assert updated is not None
        self.assertIsNotNone(updated.embedding)
        assert updated.embedding is not None
        self.assertEqual(updated.embedding[0], 0.25)

    def test_merge_candidates_demotes_transient_global_memory_to_working(self):
        merged = self.store.merge_candidates(
            candidates=[
                MemoryCandidate(
                    scope="global",
                    kind="project",
                    title="当前项目是记忆系统重构",
                    detail="这次先解决全局重复问题",
                    tags=("记忆",),
                    confidence=0.85,
                )
            ],
            user_id=self.user.id,
            conversation_id=7,
            user_message_id=201,
            assistant_message_id=202,
        )
        self.db.commit()

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].scope, "working")
        self.assertEqual(merged[0].conversation_id, 7)
        self.assertEqual(merged[0].write_policy, "session")
        self.assertIsNotNone(merged[0].expires_at)

    def test_recall_uses_database_ranked_search_when_not_using_sqlite_fts(self):
        item = self.store.create_manual_memory(
            user_id=self.user.id,
            scope="conversation",
            kind="project",
            title="KPI 重构方案",
            detail="当前正在推进 PostgreSQL memory 检索改造",
            tags=["kpi", "postgres"],
            confidence=0.9,
            pinned=False,
            active=True,
            conversation_id=42,
        )
        self.store.create_manual_memory(
            user_id=self.user.id,
            scope="conversation",
            kind="fact",
            title="天气",
            detail="今天下雨",
            tags=["daily"],
            confidence=0.6,
            pinned=False,
            active=True,
            conversation_id=42,
        )
        self.db.commit()

        self.store._uses_sqlite_memory_search = lambda: False  # type: ignore[method-assign]

        matches = self.store.recall(
            query="PostgreSQL KPI 改造",
            user_id=self.user.id,
            conversation_id=42,
            limit=4,
        )

        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0].memory_id, item.id)
        self.assertGreater(matches[0].score, 0.0)

    def test_memory_recall_accepts_array_like_query_embedding_without_boolean_coercion(self):
        item = self.store.create_manual_memory(
            user_id=self.user.id,
            scope="conversation",
            kind="project",
            title="数组查询",
            detail="召回时 query embedding 不能直接放进 if",
            tags=[],
            confidence=0.9,
            pinned=False,
            active=True,
            conversation_id=42,
        )
        self.db.commit()

        matches = self.store.recall(
            query="数组查询",
            user_id=self.user.id,
            conversation_id=42,
            limit=3,
            query_embedding=_ArrayLikeEmbedding(),  # type: ignore[arg-type]
        )

        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0].memory_id, item.id)

    def test_update_manual_memory_rebuilds_previous_conversation_document(self):
        memory = self.store.create_manual_memory(
            user_id=self.user.id,
            scope="conversation",
            kind="fact",
            title="旧会话偏好",
            detail="这个偏好只属于会话 7",
            tags=[],
            confidence=0.9,
            pinned=False,
            active=True,
            conversation_id=7,
        )
        self.db.commit()

        before = self.db.scalar(
            select(MemoryDocument).where(
                MemoryDocument.user_id == self.user.id,
                MemoryDocument.conversation_id == 7,
                MemoryDocument.doc_type == "conversation_brief",
            )
        )
        self.assertIsNotNone(before)
        assert before is not None
        self.assertIn("旧会话偏好", before.content)

        self.store.update_manual_memory(
            memory,
            user_id=self.user.id,
            scope="global",
            kind="fact",
            title="全局偏好",
            detail="这个偏好应该跨会话生效",
            tags=[],
            confidence=0.9,
            pinned=False,
            active=True,
            conversation_id=None,
        )
        self.db.commit()

        after = self.db.scalar(
            select(MemoryDocument).where(
                MemoryDocument.user_id == self.user.id,
                MemoryDocument.conversation_id == 7,
                MemoryDocument.doc_type == "conversation_brief",
            )
        )
        self.assertIsNone(after)

    def test_expiring_working_memory_rebuilds_conversation_document(self):
        memory = self.store.upsert_auto_memory(
            candidate=MemoryCandidate(
                scope="working",
                kind="project",
                title="临时上下文",
                detail="这条内容只应该短期存在",
                tags=("临时",),
                confidence=0.9,
            ),
            user_id=self.user.id,
            conversation_id=8,
            status="active",
            confidence_state="inferred",
            source_type="auto",
            modality="text",
            write_policy="session",
            pinned=False,
            expires_at=utcnow() + timedelta(hours=1),
            user_message_id=1,
            assistant_message_id=2,
        )
        self.store.rebuild_documents(user_id=self.user.id, conversation_id=8)
        self.db.commit()

        before = self.db.scalar(
            select(MemoryDocument).where(
                MemoryDocument.user_id == self.user.id,
                MemoryDocument.conversation_id == 8,
                MemoryDocument.doc_type == "conversation_brief",
            )
        )
        self.assertIsNotNone(before)
        assert before is not None
        self.assertIn("临时上下文", before.content)

        assert memory is not None
        memory.expires_at = utcnow() - timedelta(minutes=1)
        self.db.add(memory)
        self.db.commit()

        self.store.expire_stale_working_memory(user_id=self.user.id)
        self.db.commit()

        after = self.db.scalar(
            select(MemoryDocument).where(
                MemoryDocument.user_id == self.user.id,
                MemoryDocument.conversation_id == 8,
                MemoryDocument.doc_type == "conversation_brief",
            )
        )
        self.assertIsNone(after)

    def test_repeated_preference_promotes_to_confirmed_global_memory(self):
        first = self.store.upsert_auto_memory(
            candidate=MemoryCandidate(
                scope="conversation",
                kind="preference",
                title="回复风格",
                detail="用户喜欢先给结论",
                tags=("偏好",),
                confidence=0.82,
            ),
            user_id=self.user.id,
            conversation_id=9,
            status="active",
            confidence_state="inferred",
            source_type="auto",
            modality="text",
            write_policy="session",
            pinned=False,
            expires_at=None,
            user_message_id=11,
            assistant_message_id=12,
        )
        self.db.commit()

        self.assertIsNotNone(first)
        assert first is not None
        self.assertEqual(first.scope, "conversation")
        self.assertEqual(first.confidence_state, "inferred")
        self.assertEqual(first.evidence_count, 1)

        second = self.store.upsert_auto_memory(
            candidate=MemoryCandidate(
                scope="conversation",
                kind="preference",
                title="回复风格",
                detail="用户喜欢先给结论",
                tags=("偏好",),
                confidence=0.88,
            ),
            user_id=self.user.id,
            conversation_id=10,
            status="active",
            confidence_state="inferred",
            source_type="auto",
            modality="text",
            write_policy="session",
            pinned=False,
            expires_at=None,
            user_message_id=21,
            assistant_message_id=22,
        )
        self.db.commit()

        self.assertEqual(second.id, first.id)
        self.assertEqual(second.scope, "global")
        self.assertIsNone(second.conversation_id)
        self.assertEqual(second.confidence_state, "confirmed")
        self.assertEqual(second.evidence_count, 2)
        self.assertEqual(len(second.evidence), 2)

    def test_conflicting_style_preference_rejects_previous_memory(self):
        old = self.store.upsert_auto_memory(
            candidate=MemoryCandidate(
                scope="global",
                kind="preference",
                title="回复风格",
                detail="用户喜欢简短直接的回答",
                tags=("偏好",),
                confidence=0.9,
            ),
            user_id=self.user.id,
            conversation_id=11,
            status="active",
            confidence_state="confirmed",
            source_type="promoted",
            modality="text",
            write_policy="explicit",
            pinned=False,
            expires_at=None,
            user_message_id=31,
            assistant_message_id=32,
        )
        self.db.commit()

        new = self.store.upsert_auto_memory(
            candidate=MemoryCandidate(
                scope="global",
                kind="preference",
                title="回复风格",
                detail="用户现在喜欢详细展开的回答",
                tags=("偏好",),
                confidence=0.92,
                action="replace",
            ),
            user_id=self.user.id,
            conversation_id=11,
            status="active",
            confidence_state="confirmed",
            source_type="promoted",
            modality="text",
            write_policy="explicit",
            pinned=False,
            expires_at=None,
            user_message_id=41,
            assistant_message_id=42,
        )
        self.db.commit()

        self.db.refresh(old)
        self.assertEqual(old.status, "archived")
        self.assertFalse(old.active)
        self.assertEqual(old.confidence_state, "rejected")
        self.assertIsNotNone(new)
        assert new is not None
        self.assertNotEqual(new.id, old.id)
        self.assertEqual(new.confidence_state, "confirmed")

    def test_past_chat_recall_uses_turn_excerpt_without_summary(self):
        source_conversation = Conversation(user_id=self.user.id, title="记忆功能讨论", model="test:model")
        current_conversation = Conversation(user_id=self.user.id, title="当前问题", model="test:model")
        self.db.add_all([source_conversation, current_conversation])
        self.db.flush()
        user_message = Message(
            conversation_id=source_conversation.id,
            role="user",
            content="Chatchat 记忆系统要补候选确认面板",
        )
        assistant_message = Message(
            conversation_id=source_conversation.id,
            role="assistant",
            content="候选记忆应该靠近刚刚触发它的回答展示。",
        )
        self.db.add_all([user_message, assistant_message])
        self.db.flush()

        entry = ChatHistoryRecallStore(self.db).upsert_turn(
            user_id=self.user.id,
            conversation=source_conversation,
            user_message=user_message,
            assistant_message=assistant_message,
            summary="",
        )
        self.db.commit()

        self.assertIsNotNone(entry)
        refs = ChatHistoryRecallStore(self.db).recall(
            user_id=self.user.id,
            conversation_id=current_conversation.id,
            query="候选确认面板",
            limit=3,
        )

        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].conversation_id, source_conversation.id)
        self.assertEqual(refs[0].summary, "")
        self.assertIn("候选确认面板", refs[0].excerpt)

    def test_past_chat_recall_accepts_array_like_embeddings_without_boolean_coercion(self):
        source_conversation = Conversation(user_id=self.user.id, title="数组历史", model="test:model")
        current_conversation = Conversation(user_id=self.user.id, title="当前问题", model="test:model")
        self.db.add_all([source_conversation, current_conversation])
        self.db.flush()
        user_message = Message(
            conversation_id=source_conversation.id,
            role="user",
            content="历史索引里保存数组向量",
        )
        assistant_message = Message(
            conversation_id=source_conversation.id,
            role="assistant",
            content="后续召回不应该触发 numpy 布尔错误。",
        )
        self.db.add_all([user_message, assistant_message])
        self.db.flush()

        entry = ChatHistoryRecallStore(self.db).upsert_turn(
            user_id=self.user.id,
            conversation=source_conversation,
            user_message=user_message,
            assistant_message=assistant_message,
            summary="数组向量历史索引。",
            embedding=_ArrayLikeEmbedding(),  # type: ignore[arg-type]
        )
        self.db.commit()

        self.assertIsNotNone(entry)
        assert entry is not None
        refs = ChatHistoryRecallStore(self.db).recall(
            user_id=self.user.id,
            conversation_id=current_conversation.id,
            query="数组 向量",
            limit=3,
            query_embedding=_ArrayLikeEmbedding(),  # type: ignore[arg-type]
        )

        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0].conversation_id, source_conversation.id)

    def test_memory_settings_and_clear_policies_are_persisted(self):
        source_conversation = Conversation(user_id=self.user.id, title="历史对话", model="test:model")
        self.db.add(source_conversation)
        self.db.flush()
        user_message = Message(
            conversation_id=source_conversation.id,
            role="user",
            content="记住我的项目叫 Chatchat",
        )
        assistant_message = Message(
            conversation_id=source_conversation.id,
            role="assistant",
            content="已记录项目名称。",
        )
        self.db.add_all([user_message, assistant_message])
        self.db.flush()
        self.store.create_manual_memory(
            user_id=self.user.id,
            scope="global",
            kind="project",
            title="项目",
            detail="用户当前项目叫 Chatchat",
            tags=["项目"],
            confidence=0.9,
            pinned=False,
            active=True,
            conversation_id=None,
        )
        ChatHistoryRecallStore(self.db).upsert_turn(
            user_id=self.user.id,
            conversation=source_conversation,
            user_message=user_message,
            assistant_message=assistant_message,
            summary="用户在做 Chatchat 项目。",
        )
        self.db.commit()

        settings_store = MemorySettingsStore(self.db)
        settings = settings_store.update(
            user_id=self.user.id,
            saved_memories_enabled=False,
            reference_chat_history_enabled=False,
            memory_learning_enabled=False,
            sensitive_memory_enabled=True,
        )
        self.db.commit()

        self.assertFalse(settings.saved_memories_enabled)
        self.assertFalse(settings.reference_chat_history_enabled)
        self.assertFalse(settings.memory_learning_enabled)
        self.assertTrue(settings.sensitive_memory_enabled)
        self.assertEqual(settings_store.clear_saved_memories(user_id=self.user.id), 1)
        self.assertEqual(settings_store.clear_chat_history_index(user_id=self.user.id), 1)
        self.db.commit()
        self.assertEqual(self.db.scalars(select(MemoryItem)).all(), [])
        self.assertEqual(self.db.scalars(select(MemoryDocument)).all(), [])
        self.assertEqual(self.db.scalars(select(ChatHistoryEntry)).all(), [])


if __name__ == "__main__":
    unittest.main()
