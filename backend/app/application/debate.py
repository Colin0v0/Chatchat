from __future__ import annotations

from fastapi import Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..runtime.requests import DebateAskRequest, DebateDecisionRequest, DebateNextRequest
from ..schemas import DebateJudgeAskIn, DebateJudgeDecisionIn
from ..storage.models import DebateSession
from .streaming import stream_mode_action


def advance_debate_session_response(*, db: Session, request: Request, session: DebateSession) -> StreamingResponse:
    return stream_mode_action(
        mode_name="debate",
        action="next",
        request=DebateNextRequest(
            db=db,
            request=request,
            session=session,
        ),
    )


def ask_debate_judge_question_response(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    payload: DebateJudgeAskIn,
) -> StreamingResponse:
    return stream_mode_action(
        mode_name="debate",
        action="ask",
        request=DebateAskRequest(
            db=db,
            request=request,
            session=session,
            payload=payload,
        ),
    )


def create_debate_judge_decision_response(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    payload: DebateJudgeDecisionIn,
) -> StreamingResponse:
    return stream_mode_action(
        mode_name="debate",
        action="decision",
        request=DebateDecisionRequest(
            db=db,
            request=request,
            session=session,
            payload=payload,
        ),
    )
