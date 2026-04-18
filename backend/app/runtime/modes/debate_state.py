from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime

from sqlalchemy.orm import Session

from ...debate.common import (
    _advance_after_generated_turn,
    _decision_payload,
    _ensure_free_debate_state,
    _free_debate_clock_event_line,
    _is_free_debate_over,
    _next_stage,
    _next_turn_index,
    _resolve_next_participant,
    _turn_payload,
    load_debate_session_for_user,
)
from ...schemas import DebateJudgeDecisionIn
from ...storage.models import DebateJudgeDecision, DebateSession, DebateTurn


def commit_session_state(db: Session, session: DebateSession, *, refresh_turns: bool = False) -> DebateSession:
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)
    if refresh_turns:
        db.refresh(session, attribute_names=["turns", "participants"])
    return session


def emit_stage_events(session: DebateSession, stage_changes: list[str]) -> Iterator[str]:
    for stage in stage_changes:
        yield json.dumps(
            {"type": "stage_changed", "stage": stage, "status": session.status},
            ensure_ascii=False,
        ) + "\n"
        if stage == "free_debate":
            clock_event = _free_debate_clock_event_line(session)
            if clock_event:
                yield clock_event


def resolve_next_debate_participant(
    db: Session,
    session: DebateSession,
) -> tuple[object | None, list[str]]:
    participant, stage_changes = _resolve_next_participant(session)
    commit_session_state(db, session)
    return participant, stage_changes


def advance_after_speaker_turn(db: Session, session: DebateSession, completed_stage: str) -> list[str]:
    stage_changes = _advance_after_generated_turn(session, completed_stage)
    commit_session_state(db, session)
    return stage_changes


def maybe_advance_free_debate_after_question(db: Session, session: DebateSession) -> list[str]:
    state = _ensure_free_debate_state(session)
    if state is None or not _is_free_debate_over(session, state):
        return []
    session.stage = _next_stage(session, "free_debate")
    session.status = "running" if session.stage != "judge_decision" else "waiting_judge"
    commit_session_state(db, session)
    return [session.stage]


def create_judge_question_turn(db: Session, session: DebateSession, question: str) -> DebateTurn:
    question_turn = DebateTurn(
        session=session,
        kind="judge_question",
        stage=session.stage,
        turn_index=_next_turn_index(session),
        prompt_snapshot="",
        content=question.strip(),
    )
    session.updated_at = datetime.utcnow()
    db.add(question_turn)
    db.add(session)
    db.commit()
    db.refresh(question_turn)
    return question_turn


def finalize_debate_decision(
    db: Session,
    session: DebateSession,
    payload: DebateJudgeDecisionIn,
) -> DebateSession:
    if session.judge_decision is None:
        decision = DebateJudgeDecision(session=session)
    else:
        decision = session.judge_decision

    decision.winner_side = payload.winner_side
    decision.judge_comment = payload.judge_comment.strip()
    decision.scoring_json = json.dumps(payload.scoring_json or {}, ensure_ascii=False)
    db.add(decision)
    db.flush()

    session.status = "finished"
    session.stage = "judge_decision"
    session.finished_at = datetime.utcnow()
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)
    return load_debate_session_for_user(db=db, session_id=session.id, user_id=session.user_id)


def build_judge_question_event(question_turn: DebateTurn) -> str:
    return json.dumps(
        {"type": "judge_question", "turn": _turn_payload(question_turn).model_dump(mode="json")},
        ensure_ascii=False,
    ) + "\n"


def build_decision_saved_event(session: DebateSession) -> str:
    return json.dumps(
        {
            "type": "decision_saved",
            "judge_decision": _decision_payload(session.judge_decision).model_dump(mode="json"),
            "status": session.status,
            "stage": session.stage,
        },
        ensure_ascii=False,
    ) + "\n"
