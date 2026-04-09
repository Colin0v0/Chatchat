import asyncio
import unittest
from types import SimpleNamespace

from app.memory.service import MemoryService


class _StubMemoryService(MemoryService):
    def __init__(self):
        super().__init__(
            SimpleNamespace(
                memory_extract_max_items=2,
                memory_model="",
                memory_recall_top_k=2,
                memory_refresh_max_concurrency=1,
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


if __name__ == "__main__":
    unittest.main()
