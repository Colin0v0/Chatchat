from __future__ import annotations

from ...debate.common import _free_debate_state, _next_free_debate_side, _participant_by_side
from ...storage.models import DebateParticipant, DebateSession


def debate_session_finished(session: DebateSession) -> bool:
    return session.status == "finished"


def resolve_question_target_sides(ask_to: str) -> tuple[str, ...]:
    return ("pro", "con") if ask_to == "all" else (ask_to,)


def should_stream_question_reply_to_side(*, session: DebateSession, side: str) -> bool:
    if session.stage != "free_debate":
        return True
    state = _free_debate_state(session)
    if state is None:
        return True
    if side == "pro":
        return int(state["pro_remaining_ms"]) > 0
    return int(state["con_remaining_ms"]) > 0


def should_continue_free_debate_turn_loop(*, active_stage: str, session: DebateSession) -> bool:
    return active_stage == "free_debate" and session.stage == "free_debate"


def next_free_debate_participant(session: DebateSession) -> DebateParticipant:
    return participant_for_side(session, _next_free_debate_side(session))


def participant_for_side(session: DebateSession, side: str) -> DebateParticipant:
    return _participant_by_side(session, side)


def should_restore_pre_question_status(*, session: DebateSession, question_stage: str) -> bool:
    return session.stage == question_stage


def decision_summary_context(session: DebateSession) -> tuple[str, str]:
    decision = session.judge_decision
    if decision is None:
        return "draw", ""
    return decision.winner_side, decision.judge_comment
