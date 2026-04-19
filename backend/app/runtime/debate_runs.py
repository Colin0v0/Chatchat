from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import Request

from ..schemas import DebateJudgeAskIn, DebateJudgeDecisionIn
from ..storage.database import SessionLocal
from ..storage.models import DebateSession
from ..debate.common import load_debate_session_for_user
from .resume_protocol import StoredRunEvent, create_run_id, encode_resumable_event

logger = logging.getLogger("chatchat.debate.runs")

DebateRunAction = str


class BackgroundDebateRequest:
    def __init__(self, app):
        self.app = app

    async def is_disconnected(self) -> bool:
        return False


@dataclass(slots=True)
class DebateActiveRunState:
    session_id: int
    user_id: int
    action: DebateRunAction
    run_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    events: list[StoredRunEvent] = field(default_factory=list)
    next_seq: int = 0
    subscribers: set[asyncio.Queue[str | None]] = field(default_factory=set)
    task: asyncio.Task[None] | None = None
    completed: bool = False


class DebateRunRegistry:
    def __init__(self) -> None:
        self._runs: dict[int, DebateActiveRunState] = {}
        self._lock = asyncio.Lock()

    async def describe(self, session_id: int) -> dict[str, object] | None:
        async with self._lock:
            state = self._runs.get(session_id)
            if state is None or state.completed:
                return None
            return {
                "action": state.action,
                "run_id": state.run_id,
                "started_at": state.started_at.astimezone(timezone.utc).isoformat(timespec="milliseconds"),
            }

    async def start_or_attach(
        self,
        *,
        app,
        session: DebateSession,
        action: DebateRunAction,
        runner_factory: Callable[[BackgroundDebateRequest], AsyncIterator[str]],
    ) -> AsyncIterator[str]:
        async with self._lock:
            state = self._runs.get(session.id)
            if state is not None and not state.completed:
                if state.action != action:
                    raise RuntimeError(f"Debate session is already running action '{state.action}'.")
                return self._subscribe_iterator(state)

            state = DebateActiveRunState(
                session_id=session.id,
                user_id=session.user_id,
                action=action,
                run_id=create_run_id(),
            )
            self._runs[session.id] = state
            state.task = asyncio.create_task(
                self._execute_run(
                    state=state,
                    app=app,
                    runner_factory=runner_factory,
                ),
                name=f"debate-run-{session.id}-{action}",
            )
            return self._subscribe_iterator(state)

    async def attach_existing(
        self,
        session_id: int,
        *,
        after_seq: int | None = None,
    ) -> AsyncIterator[str] | None:
        async with self._lock:
            state = self._runs.get(session_id)
            if state is None or state.completed:
                return None
            return self._subscribe_iterator(state, after_seq=after_seq)

    def _subscribe_iterator(
        self,
        state: DebateActiveRunState,
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

    async def _publish(self, state: DebateActiveRunState, line: str) -> None:
        raw_line = line[:-1] if line.endswith("\n") else line
        async with self._lock:
            next_seq = state.next_seq + 1
            normalized = encode_resumable_event(raw_line, run_id=state.run_id, seq=next_seq)
            state.events.append(StoredRunEvent(seq=next_seq, line=normalized))
            state.next_seq = next_seq
            subscribers = tuple(state.subscribers)
        for subscriber in subscribers:
            await subscriber.put(normalized)

    async def _finish(self, state: DebateActiveRunState) -> None:
        async with self._lock:
            state.completed = True
            subscribers = tuple(state.subscribers)
            state.subscribers.clear()
            current = self._runs.get(state.session_id)
            if current is state:
                del self._runs[state.session_id]
        for subscriber in subscribers:
            await subscriber.put(None)

    async def _execute_run(
        self,
        *,
        state: DebateActiveRunState,
        app,
        runner_factory: Callable[[BackgroundDebateRequest], AsyncIterator[str]],
    ) -> None:
        request = BackgroundDebateRequest(app)
        try:
            runner = runner_factory(request)
            async for line in runner:
                await self._publish(state, line)
        except Exception as exc:
            logger.exception(
                "debate background run failed | session_id=%s | action=%s",
                state.session_id,
                state.action,
            )
            await self._publish(
                state,
                json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n",
            )
        finally:
            await self._finish(state)


def get_debate_run_registry(request: Request) -> DebateRunRegistry:
    return request.app.state.debate_run_registry


def build_debate_next_runner(*, session_id: int, user_id: int):
    from .modes.debate_actions import debate_next_event_stream

    async def runner(request: BackgroundDebateRequest):
        db = SessionLocal()
        try:
            session = load_debate_session_for_user(db=db, session_id=session_id, user_id=user_id)
            async for line in debate_next_event_stream(
                db=db,
                request=request,  # type: ignore[arg-type]
                session=session,
            ):
                yield line
        finally:
            db.close()

    return runner


def build_debate_ask_runner(*, session_id: int, user_id: int, payload: DebateJudgeAskIn):
    from .modes.debate_actions import debate_ask_event_stream

    async def runner(request: BackgroundDebateRequest):
        db = SessionLocal()
        try:
            session = load_debate_session_for_user(db=db, session_id=session_id, user_id=user_id)
            async for line in debate_ask_event_stream(
                db=db,
                request=request,  # type: ignore[arg-type]
                session=session,
                payload=payload,
            ):
                yield line
        finally:
            db.close()

    return runner


def build_debate_decision_runner(*, session_id: int, user_id: int, payload: DebateJudgeDecisionIn):
    from .modes.debate_actions import debate_decision_event_stream

    async def runner(request: BackgroundDebateRequest):
        db = SessionLocal()
        try:
            session = load_debate_session_for_user(db=db, session_id=session_id, user_id=user_id)
            async for line in debate_decision_event_stream(
                db=db,
                request=request,  # type: ignore[arg-type]
                session=session,
                payload=payload,
            ):
                yield line
        finally:
            db.close()

    return runner
