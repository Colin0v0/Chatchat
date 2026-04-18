from __future__ import annotations

import json
from collections.abc import Iterator

from ...debate.common import (
    _decision_payload,
    _free_debate_clock_event_line,
    _turn_payload,
)
from ...storage.models import DebateSession, DebateTurn
from .debate_runtime import DebateStageTransition


def emit_stage_events(session: DebateSession, transition: DebateStageTransition) -> Iterator[str]:
    for stage in transition.stage_changes:
        yield json.dumps(
            {"type": "stage_changed", "stage": stage, "status": session.status},
            ensure_ascii=False,
        ) + "\n"
        if stage == "free_debate":
            clock_event = _free_debate_clock_event_line(session)
            if clock_event:
                yield clock_event


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
