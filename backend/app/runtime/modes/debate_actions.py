from __future__ import annotations

import json

from fastapi import Request
from sqlalchemy.orm import Session

from ...debate.common import (
    _normalize_decision_scoring,
)
from ...schemas import DebateJudgeAskIn, DebateJudgeDecisionIn
from ...runtime.run_trace import RunTraceRecorder
from ...storage.models import DebateSession
from .debate_policies import (
    debate_session_finished,
    resolve_question_target_sides,
    should_restore_pre_question_status,
)
from .debate_runtime import DebateJudgeQuestionContext, DebateRuntimeContext
from .debate_stage_handlers import stream_decision_summary_flow, stream_stage_followup_events
from .debate_steps import DebateStreamInterrupted
from .debate_state import (
    build_decision_saved_event,
    build_judge_question_event,
)
from .debate_turn_handlers import stream_next_turn_rounds, stream_question_reply_rounds


def _error_event_line(message: str) -> str:
    return json.dumps({"type": "error", "message": message}, ensure_ascii=False) + "\n"


def _error_event_payload(message: str) -> dict[str, object]:
    return {"type": "error", "message": message}


def _done_event_line(session: DebateSession) -> str:
    return json.dumps(
        {"type": "done", "stage": session.stage, "status": session.status},
        ensure_ascii=False,
    ) + "\n"


def _done_event_payload(session: DebateSession) -> dict[str, object]:
    return {"type": "done", "stage": session.stage, "status": session.status}


def _debate_trace(db: Session, session: DebateSession, action: str) -> RunTraceRecorder:
    return RunTraceRecorder.create(
        db=db,
        conversation_id=None,
        user_id=session.user_id,
        request_message_id=None,
        mode="debate",
        model_id="debate:multi-model",
        provider_family="debate",
        reasoning_profile="auto",
        metadata={"session_id": session.id, "action": action, "stage": session.stage},
    )


async def debate_next_event_stream(*, db: Session, request: Request, session: DebateSession):
    context = DebateRuntimeContext(db=db, request=request, session=session)
    trace = _debate_trace(db, session, "next")
    if debate_session_finished(session):
        line = trace.persist_failure_payload(
            error_code="DebateAlreadyFinished",
            error_message="Debate session already finished.",
            failure_payload=_error_event_payload("Debate session already finished."),
        )
        if line:
            yield line
        return

    participant, transition = context.persistence.resolve_next_participant(session)

    try:
        async for event in stream_stage_followup_events(
            context=context,
            transition=transition,
        ):
            yield trace.emit_ndjson_line(event)
    except DebateStreamInterrupted:
        trace.persist_failure_payload(
            error_code="DebateStreamInterrupted",
            error_message="Debate next stream interrupted.",
        )
        return

    if participant is None:
        for line in trace.persist_completion_payloads(
            response_message_id=None,
            terminal_payloads=[_done_event_payload(session)],
        ):
            yield line
        return

    try:
        async for event in stream_next_turn_rounds(
            context=context,
            participant=participant,
        ):
            yield trace.emit_ndjson_line(event)
    except DebateStreamInterrupted:
        trace.persist_failure_payload(
            error_code="DebateStreamInterrupted",
            error_message="Debate next stream interrupted.",
        )
        return

    for line in trace.persist_completion_payloads(
        response_message_id=None,
        terminal_payloads=[_done_event_payload(session)],
    ):
        yield line


async def debate_ask_event_stream(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    payload: DebateJudgeAskIn,
):
    context = DebateRuntimeContext(db=db, request=request, session=session)
    trace = _debate_trace(db, session, "ask")
    if debate_session_finished(session):
        line = trace.persist_failure_payload(
            error_code="DebateAlreadyFinished",
            error_message="Debate session already finished.",
            failure_payload=_error_event_payload("Debate session already finished."),
        )
        if line:
            yield line
        return

    if session.status == "created":
        session.status = "running"

    question_context = DebateJudgeQuestionContext(
        question_turn=context.persistence.create_judge_question_turn(session, payload.question),
        question=payload.question.strip(),
        target_sides=resolve_question_target_sides(payload.ask_to),
        previous_status=session.status,
    )

    yield trace.emit_ndjson_line(build_judge_question_event(question_context.question_turn))

    if session.stage == "free_debate":
        transition = context.persistence.maybe_advance_free_debate_after_question(session)
        if transition:
            try:
                async for event in stream_stage_followup_events(
                    context=context,
                    transition=transition,
                ):
                    yield trace.emit_ndjson_line(event)
            except DebateStreamInterrupted:
                trace.persist_failure_payload(
                    error_code="DebateStreamInterrupted",
                    error_message="Debate ask stream interrupted.",
                )
                return
            for line in trace.persist_completion_payloads(
                response_message_id=None,
                terminal_payloads=[_done_event_payload(session)],
            ):
                yield line
            return

    try:
        async for event in stream_question_reply_rounds(
            context=context,
            question_context=question_context,
        ):
            yield trace.emit_ndjson_line(event)
    except DebateStreamInterrupted:
        trace.persist_failure_payload(
            error_code="DebateStreamInterrupted",
            error_message="Debate ask stream interrupted.",
        )
        return

    if should_restore_pre_question_status(
        session=session,
        question_stage=question_context.question_turn.stage,
    ):
        session.status = question_context.previous_status
    context.replace_session(context.persistence.commit_session(session))

    for line in trace.persist_completion_payloads(
        response_message_id=None,
        terminal_payloads=[_done_event_payload(session)],
    ):
        yield line


async def debate_decision_event_stream(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    payload: DebateJudgeDecisionIn,
):
    context = DebateRuntimeContext(db=db, request=request, session=session)
    trace = _debate_trace(db, session, "decision")
    resolved_winner, resolved_scoring = _normalize_decision_scoring(
        winner_side=payload.winner_side,
        scoring_json=payload.scoring_json or {},
    )
    resolved_payload = DebateJudgeDecisionIn(
        winner_side=resolved_winner,
        judge_comment=payload.judge_comment,
        scoring_json=resolved_scoring,
    )
    session = context.replace_session(
        context.persistence.finalize_debate_decision(session, resolved_payload)
    )

    yield trace.emit_ndjson_line(build_decision_saved_event(session))

    try:
        async for event in stream_decision_summary_flow(
            context=context,
        ):
            yield trace.emit_ndjson_line(event)
    except DebateStreamInterrupted:
        trace.persist_failure_payload(
            error_code="DebateStreamInterrupted",
            error_message="Debate decision stream interrupted.",
        )
        return

    for line in trace.persist_completion_payloads(
        response_message_id=None,
        terminal_payloads=[_done_event_payload(session)],
    ):
        yield line
