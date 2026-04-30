import asyncio
import unittest
from types import SimpleNamespace

from app.memory.service import MemoryService
from app.memory.types import MemoryCandidate, MemoryTurnPolicy


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
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                raise
        if user_message_id == 2:
            self.second_job_started.set()
        self.finished.append(user_message_id)


class MemoryServiceSchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_schedule_refresh_replaces_stale_job_for_same_conversation(self):
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
        await asyncio.wait_for(service.second_job_started.wait(), timeout=1)
        await asyncio.sleep(0)

        self.assertEqual(service.started, [1, 2])
        self.assertEqual(service.finished, [2])


class MemoryServiceAutoResolutionTests(unittest.TestCase):
    def setUp(self):
        self.service = _StubMemoryService()
        self.policy = MemoryTurnPolicy(
            explicit_request=False,
            target_scope=None,
            allow_global=False,
            allow_auto_candidates=True,
            store_working_memory=True,
            skip_due_to_attachments=False,
            modality="text",
            write_policy="auto_candidate",
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
        candidate, status, expires_at, write_policy = resolved
        self.assertEqual(candidate.scope, "global")
        self.assertEqual(status, "active")
        self.assertIsNone(expires_at)
        self.assertEqual(write_policy, "explicit")

    def test_auto_general_fact_stays_candidate(self):
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
        candidate, status, expires_at, write_policy = resolved
        self.assertEqual(candidate.scope, "conversation")
        self.assertEqual(status, "candidate")
        self.assertIsNone(expires_at)
        self.assertEqual(write_policy, "auto_candidate")


if __name__ == "__main__":
    unittest.main()
