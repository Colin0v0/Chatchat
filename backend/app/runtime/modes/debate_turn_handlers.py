from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.orm import Session

from ...debate.common import _latest_opponent_turn, _next_turn_index
from ...storage.models import DebateSession, DebateTurn
from .debate_policies import (
    next_free_debate_participant,
    participant_for_side,
    should_continue_free_debate_turn_loop,
    should_stream_question_reply_to_side,
)
from .debate_stage_handlers import stream_stage_followup_events
from .debate_state import advance_after_speaker_turn
from .debate_steps import stream_participant_turn_events


async def stream_next_turn_rounds(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    participant,
) -> AsyncIterator[str]:
    current_participant = participant
    while True:
        active_stage = session.stage
        target_turn = _latest_opponent_turn(session, current_participant.side)
        async for event in stream_participant_turn_events(
            db=db,
            request=request,
            session=session,
            participant=current_participant,
            stage=active_stage,
            next_turn_index=_next_turn_index(session),
            target_turn_id=target_turn.id if target_turn else None,
        ):
            yield event

        stage_changes = advance_after_speaker_turn(db, session, active_stage)
        async for event in stream_stage_followup_events(
            db=db,
            request=request,
            session=session,
            stage_changes=stage_changes,
        ):
            yield event

        if "judge_decision" in stage_changes:
            break
        if not should_continue_free_debate_turn_loop(active_stage=active_stage, session=session):
            break

        current_participant = next_free_debate_participant(session)


async def stream_question_reply_rounds(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    target_sides: tuple[str, ...],
    question_turn: DebateTurn,
    judge_question: str,
) -> AsyncIterator[str]:
    for side in target_sides:
        if not should_stream_question_reply_to_side(session=session, side=side):
            continue
        participant = participant_for_side(session, side)
        async for event in stream_participant_turn_events(
            db=db,
            request=request,
            session=session,
            participant=participant,
            stage=session.stage,
            next_turn_index=_next_turn_index(session),
            target_turn_id=question_turn.id,
            judge_question=judge_question,
        ):
            yield event

        if session.stage != "free_debate":
            continue

        stage_changes = advance_after_speaker_turn(db, session, "free_debate")
        async for event in stream_stage_followup_events(
            db=db,
            request=request,
            session=session,
            stage_changes=stage_changes,
        ):
            yield event
        if session.stage != "free_debate":
            break
