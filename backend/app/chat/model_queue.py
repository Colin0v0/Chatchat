from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field

from ..llm.capabilities import normalize_model


@dataclass
class _QueueEntry:
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    active: bool = False


@dataclass
class _ModelQueue:
    active_count: int = 0
    waiters: deque[_QueueEntry] = field(default_factory=deque)


class ModelExecutionReservation:
    def __init__(
        self,
        *,
        coordinator: ModelExecutionCoordinator,
        model: str,
        entry: _QueueEntry,
        position: int,
    ) -> None:
        self._coordinator = coordinator
        self.model = model
        self._entry = entry
        self.position = position
        self._released = False

    @property
    def queued(self) -> bool:
        return self.position > 0

    async def wait(self) -> None:
        try:
            await self._entry.ready.wait()
        except asyncio.CancelledError:
            await self.release()
            raise

    async def release(self) -> None:
        if self._released:
            return
        self._released = True
        await self._coordinator.release(self.model, self._entry)


class ModelExecutionCoordinator:
    def __init__(self, *, max_concurrency_per_model: int = 1) -> None:
        self._max_concurrency_per_model = max(1, max_concurrency_per_model)
        self._lock = asyncio.Lock()
        self._queues: dict[str, _ModelQueue] = {}

    async def reserve(self, model: str) -> ModelExecutionReservation:
        normalized_model = normalize_model(model)
        entry = _QueueEntry()

        async with self._lock:
            queue = self._queues.setdefault(normalized_model, _ModelQueue())
            if queue.active_count < self._max_concurrency_per_model and not queue.waiters:
                queue.active_count += 1
                entry.active = True
                entry.ready.set()
                position = 0
            else:
                queue.waiters.append(entry)
                position = len(queue.waiters)

        return ModelExecutionReservation(
            coordinator=self,
            model=normalized_model,
            entry=entry,
            position=position,
        )

    async def release(self, model: str, entry: _QueueEntry) -> None:
        async with self._lock:
            queue = self._queues.get(model)
            if queue is None:
                return

            if entry.active:
                entry.active = False
                queue.active_count = max(0, queue.active_count - 1)
                while queue.waiters and queue.active_count < self._max_concurrency_per_model:
                    next_entry = queue.waiters.popleft()
                    next_entry.active = True
                    queue.active_count += 1
                    next_entry.ready.set()
                    break
            else:
                try:
                    queue.waiters.remove(entry)
                except ValueError:
                    pass

            if queue.active_count == 0 and not queue.waiters:
                self._queues.pop(model, None)
