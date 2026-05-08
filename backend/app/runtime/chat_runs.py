from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import Request

from .orchestrator import stream_chat_run
from .requests import ChatRunRequest
from .resume_protocol import StoredRunEvent, create_run_id, encode_resumable_event

logger = logging.getLogger("chatchat.chat.runs")


class BackgroundChatRequest:
    def __init__(self, app):
        self.app = app

    async def is_disconnected(self) -> bool:
        return False


class ActiveChatRunConflict(RuntimeError):
    def __init__(self, conversation_id: int, active_run: dict[str, object]):
        self.conversation_id = conversation_id
        self.active_run = active_run
        super().__init__("Conversation already has an active run.")


@dataclass(slots=True)
class ChatActiveRunState:
    conversation_id: int
    message_id: int
    run_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    events: list[StoredRunEvent] = field(default_factory=list)
    next_seq: int = 0
    subscribers: set[asyncio.Queue[str | None]] = field(default_factory=set)
    task: asyncio.Task[None] | None = None
    completed: bool = False


class ChatRunRegistry:
    def __init__(self) -> None:
        self._runs: dict[int, ChatActiveRunState] = {}
        self._lock = asyncio.Lock()

    async def describe(self, conversation_id: int) -> dict[str, object] | None:
        async with self._lock:
            state = self._runs.get(conversation_id)
            if state is None or state.completed:
                return None
            return self._describe_state(state)

    def _describe_state(self, state: ChatActiveRunState) -> dict[str, object]:
        return {
            "action": "run",
            "run_id": state.run_id,
            "last_seq": state.next_seq,
            "started_at": state.started_at.astimezone(timezone.utc).isoformat(timespec="milliseconds"),
        }

    async def start_or_attach(
        self,
        *,
        app,
        run_request: ChatRunRequest,
    ) -> AsyncIterator[str]:
        async with self._lock:
            state = self._runs.get(run_request.conversation_id)
            if state is not None and not state.completed:
                if state.message_id != run_request.message_id:
                    raise ActiveChatRunConflict(run_request.conversation_id, self._describe_state(state))
                return self._subscribe_iterator(state)

            state = ChatActiveRunState(
                conversation_id=run_request.conversation_id,
                message_id=run_request.message_id,
                run_id=create_run_id(),
            )
            self._runs[run_request.conversation_id] = state
            state.task = asyncio.create_task(
                self._execute_run(
                    state=state,
                    app=app,
                    run_request=run_request,
                ),
                name=f"chat-run-{run_request.conversation_id}-{run_request.message_id}",
            )
            return self._subscribe_iterator(state)

    async def cancel(self, conversation_id: int) -> bool:
        async with self._lock:
            state = self._runs.get(conversation_id)
            if state is None or state.completed:
                return False
            task = state.task

        if task is not None and not task.done():
            # 中文注释：用户点 Stop 时要取消后台模型流，否则前端断开了，后端仍会占着 active run。
            task.cancel()

        await self._finish(state)
        return True

    async def attach_existing(
        self,
        conversation_id: int,
        *,
        after_seq: int | None = None,
    ) -> AsyncIterator[str] | None:
        async with self._lock:
            state = self._runs.get(conversation_id)
            if state is None or state.completed:
                return None
            return self._subscribe_iterator(state, after_seq=after_seq)

    def _subscribe_iterator(
        self,
        state: ChatActiveRunState,
        *,
        after_seq: int | None = None,
    ) -> AsyncIterator[str]:
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        snapshot = [
            item.line
            for item in state.events
            if after_seq is None or item.seq > after_seq
        ]
        completed = state.completed
        if not completed:
            state.subscribers.add(queue)

        async def iterator():
            try:
                for line in snapshot:
                    yield line
                if completed:
                    return
                while True:
                    item = await queue.get()
                    if item is None:
                        return
                    yield item
            finally:
                async with self._lock:
                    state.subscribers.discard(queue)

        return iterator()

    async def _publish(self, state: ChatActiveRunState, line: str) -> None:
        raw_line = line[:-1] if line.endswith("\n") else line
        async with self._lock:
            next_seq = state.next_seq + 1
            normalized = encode_resumable_event(raw_line, run_id=state.run_id, seq=next_seq)
            state.events.append(StoredRunEvent(seq=next_seq, line=normalized))
            state.next_seq = next_seq
            subscribers = tuple(state.subscribers)
        for subscriber in subscribers:
            await subscriber.put(normalized)

    async def _finish(self, state: ChatActiveRunState) -> None:
        async with self._lock:
            if state.completed:
                return
            state.completed = True
            subscribers = tuple(state.subscribers)
            state.subscribers.clear()
            current = self._runs.get(state.conversation_id)
            if current is state:
                del self._runs[state.conversation_id]
        for subscriber in subscribers:
            await subscriber.put(None)

    async def _execute_run(
        self,
        *,
        state: ChatActiveRunState,
        app,
        run_request: ChatRunRequest,
    ) -> None:
        request = BackgroundChatRequest(app)
        try:
            async for line in stream_chat_run(
                services=run_request.services,
                request=request,  # type: ignore[arg-type]
                conversation_id=run_request.conversation_id,
                message_id=run_request.message_id,
                model=run_request.model,
                history_message_ids=run_request.history_message_ids,
                query=run_request.query,
                tool_policy=run_request.tool_policy,
                requested_reasoning=run_request.requested_reasoning,
                requested_reasoning_profile=run_request.requested_reasoning_profile,
            ):
                await self._publish(state, line)
        except Exception as exc:
            logger.exception(
                "chat background run failed | conversation_id=%s | message_id=%s",
                state.conversation_id,
                state.message_id,
            )
            await self._publish(
                state,
                json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n",
            )
        finally:
            await self._finish(state)


def get_chat_run_registry(request: Request) -> ChatRunRegistry:
    return request.app.state.chat_run_registry
