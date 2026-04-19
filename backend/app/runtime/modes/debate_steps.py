from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import Request
from sqlalchemy.orm import Session

from ...storage.models import DebateSession
from .debate_execution import run_ai_evaluation, stream_decision_summary_text, stream_speaker_turn
from .debate_runtime import DebateSpeakerTurnRequest


class DebateStreamInterrupted(Exception):
    pass


async def stream_judge_evaluation_events(
    *,
    request: Request,
    session: DebateSession,
) -> AsyncIterator[str]:
    async for event in run_ai_evaluation(request=request, session=session):
        if await request.is_disconnected():
            raise DebateStreamInterrupted()
        yield event


async def stream_participant_turn_events(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    turn_request: DebateSpeakerTurnRequest,
) -> AsyncIterator[str]:
    async for event in stream_speaker_turn(
        db=db,
        request=request,
        session=session,
        participant=turn_request.participant,
        stage=turn_request.stage,
        next_turn_index=turn_request.next_turn_index,
        target_turn_id=turn_request.target_turn_id,
        judge_question=turn_request.judge_question,
    ):
        if await request.is_disconnected():
            raise DebateStreamInterrupted()
        yield event


async def stream_decision_summary_events(
    *,
    request: Request,
    session: DebateSession,
    judge_note: str,
    winner_side: str,
    summary_chunks: list[str],
) -> AsyncIterator[str]:
    async for delta in stream_decision_summary_text(
        request=request,
        session=session,
        judge_note=judge_note,
        winner_side=winner_side,
    ):
        if await request.is_disconnected():
            raise DebateStreamInterrupted()
        summary_chunks.append(delta)
        yield json.dumps({"type": "summary_token", "content": delta}, ensure_ascii=False) + "\n"
