from __future__ import annotations

from collections.abc import AsyncIterator

from .debate_policies import decision_summary_context
from .debate_runtime import DebateRuntimeContext, DebateStageTransition
from .debate_state import emit_stage_events
from .debate_steps import (
    stream_decision_summary_events,
    stream_judge_evaluation_events,
)


async def stream_stage_followup_events(
    *,
    context: DebateRuntimeContext,
    transition: DebateStageTransition,
) -> AsyncIterator[str]:
    for event in emit_stage_events(context.session, transition):
        yield event

    if not transition.enters_judge_decision:
        return

    if transition.refresh_relations:
        context.persistence.refresh_session_relations(context.session)
    async for event in stream_judge_evaluation_events(
        request=context.request,
        session=context.session,
    ):
        yield event


async def stream_decision_summary_flow(
    *,
    context: DebateRuntimeContext,
) -> AsyncIterator[str]:
    winner_side, judge_note = decision_summary_context(context.session)
    summary_chunks: list[str] = []
    async for event in stream_decision_summary_events(
        request=context.request,
        session=context.session,
        judge_note=judge_note,
        winner_side=winner_side,
        summary_chunks=summary_chunks,
    ):
        yield event

    context.persistence.persist_decision_summary(context.session, summary_chunks)
