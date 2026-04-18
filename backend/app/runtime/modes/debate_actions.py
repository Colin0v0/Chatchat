from __future__ import annotations

import json

from fastapi import Request
from sqlalchemy.orm import Session

from ...debate.common import (
    _normalize_decision_scoring,
)
from ...schemas import DebateJudgeAskIn, DebateJudgeDecisionIn
from ...storage.models import DebateSession
from .debate_policies import (
    debate_session_finished,
    resolve_question_target_sides,
    should_restore_pre_question_status,
)
from .debate_stage_handlers import stream_decision_summary_flow, stream_stage_followup_events
from .debate_steps import DebateStreamInterrupted
from .debate_state import (
    build_decision_saved_event,
    build_judge_question_event,
    commit_session_state,
    create_judge_question_turn,
    finalize_debate_decision,
    maybe_advance_free_debate_after_question,
    resolve_next_debate_participant,
)
from .debate_turn_handlers import stream_next_turn_rounds, stream_question_reply_rounds


def _error_event_line(message: str) -> str:
    return json.dumps({"type": "error", "message": message}, ensure_ascii=False) + "\n"


def _done_event_line(session: DebateSession) -> str:
    return json.dumps(
        {"type": "done", "stage": session.stage, "status": session.status},
        ensure_ascii=False,
    ) + "\n"


async def debate_next_event_stream(*, db: Session, request: Request, session: DebateSession):
    if debate_session_finished(session):
        yield _error_event_line("Debate session already finished.")
        return

    participant, stage_changes = resolve_next_debate_participant(db, session)

    try:
        async for event in stream_stage_followup_events(
            db=db,
            request=request,
            session=session,
            stage_changes=stage_changes,
        ):
            yield event
    except DebateStreamInterrupted:
        return

    if participant is None:
        yield _done_event_line(session)
        return

    try:
        async for event in stream_next_turn_rounds(
            db=db,
            request=request,
            session=session,
            participant=participant,
        ):
            yield event
    except DebateStreamInterrupted:
        return

    yield _done_event_line(session)


async def debate_ask_event_stream(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    payload: DebateJudgeAskIn,
):
    if debate_session_finished(session):
        yield _error_event_line("Debate session already finished.")
        return

    if session.status == "created":
        session.status = "running"

    question_turn = create_judge_question_turn(db, session, payload.question)

    yield build_judge_question_event(question_turn)

    target_sides = resolve_question_target_sides(payload.ask_to)
    previous_status = session.status

    if session.stage == "free_debate":
        stage_changes = maybe_advance_free_debate_after_question(db, session)
        if stage_changes:
            try:
                async for event in stream_stage_followup_events(
                    db=db,
                    request=request,
                    session=session,
                    stage_changes=stage_changes,
                ):
                    yield event
            except DebateStreamInterrupted:
                return
            yield _done_event_line(session)
            return

    try:
        async for event in stream_question_reply_rounds(
            db=db,
            request=request,
            session=session,
            target_sides=target_sides,
            question_turn=question_turn,
            judge_question=payload.question.strip(),
        ):
            yield event
    except DebateStreamInterrupted:
        return

    if should_restore_pre_question_status(session=session, question_stage=question_turn.stage):
        session.status = previous_status
    commit_session_state(db, session)

    yield _done_event_line(session)


async def debate_decision_event_stream(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    payload: DebateJudgeDecisionIn,
):
    resolved_winner, resolved_scoring = _normalize_decision_scoring(
        winner_side=payload.winner_side,
        scoring_json=payload.scoring_json or {},
    )
    resolved_payload = DebateJudgeDecisionIn(
        winner_side=resolved_winner,
        judge_comment=payload.judge_comment,
        scoring_json=resolved_scoring,
    )
    session = finalize_debate_decision(db, session, resolved_payload)

    yield build_decision_saved_event(session)

    try:
        async for event in stream_decision_summary_flow(
            db=db,
            request=request,
            session=session,
        ):
            yield event
    except DebateStreamInterrupted:
        return

    yield _done_event_line(session)
