from __future__ import annotations

from fastapi import Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..runtime.modes import get_mode_runtime


def advance_debate_session_response(*, db: Session, request: Request, session) -> StreamingResponse:
    debate_mode = get_mode_runtime("debate")
    return StreamingResponse(
        debate_mode.stream("next", db=db, request=request, session=session),
        media_type="application/x-ndjson",
    )


def ask_debate_judge_question_response(*, db: Session, request: Request, session, payload) -> StreamingResponse:
    debate_mode = get_mode_runtime("debate")
    return StreamingResponse(
        debate_mode.stream(
            "ask",
            db=db,
            request=request,
            session=session,
            payload=payload,
        ),
        media_type="application/x-ndjson",
    )


def create_debate_judge_decision_response(*, db: Session, request: Request, session, payload) -> StreamingResponse:
    debate_mode = get_mode_runtime("debate")
    return StreamingResponse(
        debate_mode.stream("decision", db=db, request=request, session=session, payload=payload),
        media_type="application/x-ndjson",
    )
