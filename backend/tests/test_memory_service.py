import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.memory.service import MemoryService
from app.memory.types import MemoryCandidate, MemoryTurnPolicy
from app.storage.database import Base
from app.storage.models import ChatHistoryEntry, Conversation, MemoryItem, Message, User


class _StubMemoryService(MemoryService):
    def __init__(self):
        super().__init__(
            SimpleNamespace(
                memory_extract_max_items=2,
                memory_model="",
                memory_recall_top_k=2,
                memory_refresh_max_concurrency=1,
                memory_embedding_enabled=True,
                memory_vector_weight=0.75,
                memory_keyword_weight=0.25,
                memory_auto_promote_min_confidence=0.60,
                knowledge_embedding_model="text-embedding-v3",
                knowledge_embedding_base_url="",
                knowledge_embedding_api_key="",
                knowledge_embedding_dimensions=1024,
                knowledge_embedding_batch_size=8,
                knowledge_embedding_timeout_seconds=30.0,
                cache_embedding_ttl_seconds=2592000,
                cache_enabled=True,
                cache_key_prefix="chatchat",
            )
        )
        self.started: list[int] = []
        self.finished: list[int] = []
        self.first_job_started = asyncio.Event()
        self.first_job_can_finish = asyncio.Event()
        self.second_job_started = asyncio.Event()

    async def refresh_from_turn(
        self,
        *,
        conversation_id: int,
        user_message_id: int,
        assistant_message_id: int,
        response_model: str,
    ) -> None:
        self.started.append(user_message_id)
        if user_message_id == 1:
            self.first_job_started.set()
            await self.first_job_can_finish.wait()
        if user_message_id == 2:
            self.second_job_started.set()
        self.finished.append(user_message_id)


class MemoryServiceSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_schedule_refresh_queues_jobs_for_same_conversation(self):
        service = _StubMemoryService()

        service.schedule_refresh(
            conversation_id=7,
            user_message_id=1,
            assistant_message_id=11,
            response_model="openai:test",
        )
        await asyncio.wait_for(service.first_job_started.wait(), timeout=1)

        service.schedule_refresh(
            conversation_id=7,
            user_message_id=2,
            assistant_message_id=12,
            response_model="openai:test",
        )
        await asyncio.sleep(0)
        self.assertEqual(service.started, [1])
        self.assertEqual(service.finished, [])

        service.first_job_can_finish.set()
        await asyncio.wait_for(service.second_job_started.wait(), timeout=1)
        await asyncio.sleep(0)

        self.assertEqual(service.started, [1, 2])
        self.assertEqual(service.finished, [1, 2])


class MemoryServiceAutoResolutionTests(unittest.TestCase):
    def setUp(self):
        self.service = _StubMemoryService()
        self.policy = MemoryTurnPolicy(
            explicit_request=False,
            target_scope=None,
            allow_automatic_storage=True,
            skip_due_to_attachments=False,
            modality="text",
        )

    def test_auto_profile_memory_becomes_active_global(self):
        resolved = self.service._resolve_auto_memory(
            candidate=MemoryCandidate(
                scope="conversation",
                kind="profile",
                title="生日",
                detail="用户生日是May 1",
                tags=("个人", "生日"),
                confidence=0.92,
            ),
            policy=self.policy,
        )

        self.assertIsNotNone(resolved)
        assert resolved is not None
        candidate, status, confidence_state, expires_at, write_policy = resolved
        self.assertEqual(candidate.scope, "global")
        self.assertEqual(status, "active")
        self.assertEqual(confidence_state, "inferred")
        self.assertIsNone(expires_at)
        self.assertEqual(write_policy, "explicit")

    def test_auto_general_fact_stays_conversation_scoped(self):
        resolved = self.service._resolve_auto_memory(
            candidate=MemoryCandidate(
                scope="conversation",
                kind="fact",
                title="讨论主题",
                detail="用户在讨论记忆系统策略",
                tags=("记忆",),
                confidence=0.9,
            ),
            policy=self.policy,
        )

        self.assertIsNotNone(resolved)
        assert resolved is not None
        candidate, status, confidence_state, expires_at, write_policy = resolved
        self.assertEqual(candidate.scope, "conversation")
        self.assertEqual(status, "active")
        self.assertEqual(confidence_state, "inferred")
        self.assertIsNone(expires_at)
        self.assertEqual(write_policy, "session")

    def test_auto_stable_fact_becomes_active_global(self):
        resolved = self.service._resolve_auto_memory(
            candidate=MemoryCandidate(
                scope="conversation",
                kind="fact",
                title="用户生日",
                detail="用户生日是 May 1",
                tags=("个人",),
                confidence=0.9,
            ),
            policy=self.policy,
        )

        self.assertIsNotNone(resolved)
        assert resolved is not None
        candidate, status, confidence_state, expires_at, write_policy = resolved
        self.assertEqual(candidate.scope, "global")
        self.assertEqual(status, "active")
        self.assertEqual(confidence_state, "inferred")
        self.assertIsNone(expires_at)
        self.assertEqual(write_policy, "explicit")

    def test_explicit_memory_without_scope_uses_candidate_stability(self):
        resolved = self.service._resolve_auto_memory(
            candidate=MemoryCandidate(
                scope="conversation",
                kind="preference",
                title="回复风格",
                detail="用户喜欢直接给结论",
                tags=("偏好",),
                confidence=0.9,
            ),
            policy=MemoryTurnPolicy(
                explicit_request=True,
                target_scope=None,
                allow_automatic_storage=False,
                skip_due_to_attachments=False,
                modality="text",
            ),
        )

        self.assertIsNotNone(resolved)
        assert resolved is not None
        candidate, status, confidence_state, expires_at, write_policy = resolved
        self.assertEqual(candidate.scope, "global")
        self.assertEqual(status, "active")
        self.assertEqual(confidence_state, "confirmed")
        self.assertIsNone(expires_at)
        self.assertEqual(write_policy, "explicit")

    def test_explicit_local_marker_keeps_memory_conversation_scoped(self):
        resolved = self.service._resolve_auto_memory(
            candidate=MemoryCandidate(
                scope="conversation",
                kind="preference",
                title="本次回复风格",
                detail="这次用户希望回答更短",
                tags=("本次",),
                confidence=0.9,
            ),
            policy=MemoryTurnPolicy(
                explicit_request=True,
                target_scope="conversation",
                allow_automatic_storage=False,
                skip_due_to_attachments=False,
                modality="text",
            ),
        )

        self.assertIsNotNone(resolved)
        assert resolved is not None
        candidate, status, confidence_state, expires_at, write_policy = resolved
        self.assertEqual(candidate.scope, "conversation")
        self.assertEqual(status, "active")
        self.assertEqual(confidence_state, "confirmed")
        self.assertIsNone(expires_at)
        self.assertEqual(write_policy, "explicit")

    def test_low_confidence_general_fact_is_skipped(self):
        resolved = self.service._resolve_auto_memory(
            candidate=MemoryCandidate(
                scope="conversation",
                kind="fact",
                title="偶发偏好",
                detail="用户刚刚随口提了一次",
                tags=("记忆",),
                confidence=0.3,
            ),
            policy=self.policy,
        )

        self.assertIsNone(resolved)

    def test_medium_confidence_general_fact_becomes_pending(self):
        resolved = self.service._resolve_auto_memory(
            candidate=MemoryCandidate(
                scope="conversation",
                kind="fact",
                title="可能偏好",
                detail="用户可能喜欢表格，但证据还不强",
                tags=("偏好",),
                confidence=0.5,
            ),
            policy=self.policy,
        )

        self.assertIsNotNone(resolved)
        assert resolved is not None
        candidate, status, confidence_state, expires_at, write_policy = resolved
        self.assertEqual(candidate.scope, "conversation")
        self.assertEqual(status, "active")
        self.assertEqual(confidence_state, "pending")
        self.assertIsNone(expires_at)
        self.assertEqual(write_policy, "session")

    def test_relative_time_hint_accepts_timezone_aware_datetime(self):
        hint = self.service._relative_time_hint(datetime.now(timezone.utc))
        self.assertEqual(hint, "今天")


class MemoryServiceRefreshPolicyTests(unittest.IsolatedAsyncioTestCase):
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
        self.user = User(username="memory-service-user", password_hash="hash", is_active=True)
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)
        self.service = MemoryService(
            SimpleNamespace(
                memory_extract_max_items=2,
                memory_model="",
                memory_past_chat_recall_top_k=4,
                memory_recall_top_k=2,
                memory_refresh_max_concurrency=1,
                memory_embedding_enabled=False,
                memory_vector_weight=0.75,
                memory_keyword_weight=0.25,
                memory_auto_promote_min_confidence=0.60,
            )
        )

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _create_turn(
        self,
        *,
        user_text: str,
        assistant_text: str,
        temporary_chat: bool = False,
    ) -> tuple[Conversation, Message, Message]:
        conversation = Conversation(
            user_id=self.user.id,
            title="记忆策略测试",
            model="test:model",
            temporary_chat=temporary_chat,
        )
        self.db.add(conversation)
        self.db.flush()
        user_message = Message(conversation_id=conversation.id, role="user", content=user_text)
        assistant_message = Message(conversation_id=conversation.id, role="assistant", content=assistant_text)
        self.db.add_all([user_message, assistant_message])
        self.db.commit()
        self.db.refresh(conversation)
        self.db.refresh(user_message)
        self.db.refresh(assistant_message)
        return conversation, user_message, assistant_message

    async def test_temporary_chat_skips_memory_learning(self):
        conversation, user_message, assistant_message = self._create_turn(
            user_text="记住我喜欢先给结论",
            assistant_text="好的，我会先给结论。",
            temporary_chat=True,
        )
        extract_mock = AsyncMock(
            return_value=[
                MemoryCandidate(
                    scope="global",
                    kind="preference",
                    title="回复风格",
                    detail="用户喜欢先给结论",
                    tags=("偏好",),
                    confidence=0.95,
                )
            ]
        )

        with patch.object(self.service._extractor, "extract", extract_mock), patch(
            "app.memory.service.SessionLocal",
            self.session_factory,
        ):
            await self.service.refresh_from_turn(
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                response_model="test:model",
            )

        extract_mock.assert_not_awaited()
        self.assertEqual(self.db.scalars(select(MemoryItem)).all(), [])
        self.assertEqual(self.db.scalars(select(ChatHistoryEntry)).all(), [])

    async def test_sensitive_turn_is_not_indexed_or_extracted_by_default(self):
        conversation, user_message, assistant_message = self._create_turn(
            user_text="记住我的邮箱是 colin@example.com",
            assistant_text="好的。",
        )
        extract_mock = AsyncMock(
            return_value=[
                MemoryCandidate(
                    scope="global",
                    kind="profile",
                    title="邮箱",
                    detail="用户邮箱是 colin@example.com",
                    tags=("邮箱",),
                    confidence=0.95,
                )
            ]
        )

        with patch.object(self.service._extractor, "extract", extract_mock), patch(
            "app.memory.service.SessionLocal",
            self.session_factory,
        ):
            await self.service.refresh_from_turn(
                conversation_id=conversation.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                response_model="test:model",
            )

        extract_mock.assert_not_awaited()
        self.assertEqual(self.db.scalars(select(MemoryItem)).all(), [])
        self.assertEqual(self.db.scalars(select(ChatHistoryEntry)).all(), [])


if __name__ == "__main__":
    unittest.main()
