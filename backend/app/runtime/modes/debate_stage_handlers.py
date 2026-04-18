from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.orm import Session

from ...storage.models import DebateSession
from .debate_policies import decision_summary_context
from .debate_state import emit_stage_events
from .debate_steps import (
    persist_decision_summary,
    stream_decision_summary_events,
    stream_judge_evaluation_events,
)


async def stream_stage_followup_events(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    stage_changes: list[str],
) -> AsyncIterator[str]:
    for event in emit_stage_events(session, stage_changes):
        yield event

    if "judge_decision" not in stage_changes:
        return

    db.refresh(session, attribute_names=["turns", "participants"])
    async for event in stream_judge_evaluation_events(request=request, session=session):
        yield event


async def stream_decision_summary_flow(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
) -> AsyncIterator[str]:
    winner_side, judge_note = decision_summary_context(session)
    summary_chunks: list[str] = []
    async for event in stream_decision_summary_events(
        request=request,
        session=session,
        judge_note=judge_note,
        winner_side=winner_side,
        summary_chunks=summary_chunks,
    ):
        yield event

    persist_decision_summary(db=db, session=session, summary_chunks=summary_chunks)
