from __future__ import annotations

import asyncio
import unittest

from app.chat.model_queue import ModelExecutionCoordinator


class ModelExecutionCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_model_waiters_run_one_by_one(self):
        coordinator = ModelExecutionCoordinator(max_concurrency_per_model=1)

        first = await coordinator.reserve("openai:deepseek-chat")
        second = await coordinator.reserve("openai:deepseek-chat")
        third = await coordinator.reserve("openai:deepseek-chat")

        self.assertFalse(first.queued)
        self.assertTrue(second.queued)
        self.assertEqual(second.position, 1)
        self.assertEqual(third.position, 2)

        second_started = asyncio.Event()
        third_started = asyncio.Event()
        allow_second_to_finish = asyncio.Event()

        async def run_second() -> None:
            await second.wait()
            second_started.set()
            await allow_second_to_finish.wait()
            await second.release()

        async def run_third() -> None:
            await third.wait()
            third_started.set()
            await third.release()

        second_task = asyncio.create_task(run_second())
        third_task = asyncio.create_task(run_third())

        await asyncio.sleep(0)
        self.assertFalse(second_started.is_set())
        self.assertFalse(third_started.is_set())

        await first.release()
        await asyncio.wait_for(second_started.wait(), timeout=1)
        self.assertFalse(third_started.is_set())

        allow_second_to_finish.set()
        await asyncio.wait_for(third_started.wait(), timeout=1)
        await second_task
        await third_task

    async def test_different_models_can_run_in_parallel(self):
        coordinator = ModelExecutionCoordinator(max_concurrency_per_model=1)

        first = await coordinator.reserve("openai:deepseek-chat")
        second = await coordinator.reserve("openai:deepseek-reasoner")

        self.assertFalse(first.queued)
        self.assertFalse(second.queued)

        await asyncio.wait_for(first.wait(), timeout=1)
        await asyncio.wait_for(second.wait(), timeout=1)

        await first.release()
        await second.release()

    async def test_cancelled_waiter_leaves_queue_clean(self):
        coordinator = ModelExecutionCoordinator(max_concurrency_per_model=1)

        first = await coordinator.reserve("openai:deepseek-chat")
        second = await coordinator.reserve("openai:deepseek-chat")

        wait_task = asyncio.create_task(second.wait())
        await asyncio.sleep(0)
        wait_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await wait_task

        third = await coordinator.reserve("openai:deepseek-chat")
        self.assertTrue(third.queued)
        self.assertEqual(third.position, 1)

        third_started = asyncio.Event()

        async def run_third() -> None:
            await third.wait()
            third_started.set()
            await third.release()

        third_task = asyncio.create_task(run_third())
        await asyncio.sleep(0)
        self.assertFalse(third_started.is_set())

        await first.release()
        await asyncio.wait_for(third_started.wait(), timeout=1)
        await third_task

    async def test_first_three_requests_for_same_model_start_immediately(self):
        coordinator = ModelExecutionCoordinator(max_concurrency_per_model=3)

        first = await coordinator.reserve("openai:deepseek-chat")
        second = await coordinator.reserve("openai:deepseek-chat")
        third = await coordinator.reserve("openai:deepseek-chat")
        fourth = await coordinator.reserve("openai:deepseek-chat")

        self.assertFalse(first.queued)
        self.assertFalse(second.queued)
        self.assertFalse(third.queued)
        self.assertTrue(fourth.queued)
        self.assertEqual(fourth.position, 1)

        await asyncio.wait_for(first.wait(), timeout=1)
        await asyncio.wait_for(second.wait(), timeout=1)
        await asyncio.wait_for(third.wait(), timeout=1)

        fourth_started = asyncio.Event()

        async def run_fourth() -> None:
            await fourth.wait()
            fourth_started.set()
            await fourth.release()

        fourth_task = asyncio.create_task(run_fourth())
        await asyncio.sleep(0)
        self.assertFalse(fourth_started.is_set())

        await second.release()
        await asyncio.wait_for(fourth_started.wait(), timeout=1)

        await first.release()
        await third.release()
        await fourth_task


if __name__ == "__main__":
    unittest.main()
