from __future__ import annotations

from fastapi import Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..runtime.debate_runs import (
    build_debate_ask_runner,
    build_debate_decision_runner,
    build_debate_next_runner,
    get_debate_run_registry,
)
from ..runtime.streaming import ndjson_stream_response
from ..schemas import DebateJudgeAskIn, DebateJudgeDecisionIn
from ..storage.models import DebateSession


async def advance_debate_session_response(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
) -> StreamingResponse:
    stream = await get_debate_run_registry(request).start_or_attach(
        app=request.app,
        session=session,
        action="next",
        runner_factory=build_debate_next_runner(
            session_id=session.id,
            user_id=session.user_id,
        ),
    )
    return ndjson_stream_response(stream)


async def ask_debate_judge_question_response(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    payload: DebateJudgeAskIn,
) -> StreamingResponse:
    stream = await get_debate_run_registry(request).start_or_attach(
        app=request.app,
        session=session,
        action="ask",
        runner_factory=build_debate_ask_runner(
            session_id=session.id,
            user_id=session.user_id,
            payload=payload,
        ),
    )
    return ndjson_stream_response(stream)


async def create_debate_judge_decision_response(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    payload: DebateJudgeDecisionIn,
) -> StreamingResponse:
    stream = await get_debate_run_registry(request).start_or_attach(
        app=request.app,
        session=session,
        action="decision",
        runner_factory=build_debate_decision_runner(
            session_id=session.id,
            user_id=session.user_id,
            payload=payload,
        ),
    )
    return ndjson_stream_response(stream)


async def stream_active_debate_session_response(
    *,
    request: Request,
    session: DebateSession,
    after_seq: int | None = None,
) -> StreamingResponse:
    stream = await get_debate_run_registry(request).attach_existing(
        session.id,
        after_seq=after_seq,
    )
    if stream is None:
        raise RuntimeError("No active debate run.")
    return ndjson_stream_response(stream)
