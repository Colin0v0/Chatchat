from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..application import (
    advance_debate_session_response,
    ask_debate_judge_question_response,
    create_debate_judge_decision_response,
    stream_active_debate_session_response,
)
from ..auth import require_current_user
from ..core.config import settings
from ..debate.common import build_debate_session_detail, load_debate_session_for_user
from ..debate.config import DebateSessionConfig
from ..providers import resolve_model_profile
from ..runtime.debate_runs import get_debate_run_registry
from ..schemas import (
    DebateJudgeAskIn,
    DebateJudgeDecisionIn,
    DebateSessionCreateIn,
    DebateSessionDetailOut,
    DebateSessionSummaryOut,
    DebateSessionUpdateIn,
)
from ..storage.database import get_db
from ..storage.models import DebateParticipant, DebateSession, DebateTurn, User

router = APIRouter(prefix="/api/debate", tags=["debate"])


async def _debate_active_run_payload(request: Request, session_id: int) -> dict[str, str] | None:
    return await get_debate_run_registry(request).describe(session_id)


def _ensure_model_enabled(model_id: str) -> None:
    if settings.model_catalog_strict and resolve_model_profile(model_id) is None:
        raise HTTPException(status_code=400, detail=f"Model not enabled: {model_id}")


@router.get("/sessions", response_model=list[DebateSessionSummaryOut])
def list_debate_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    sessions = db.scalars(
        select(DebateSession)
        .where(DebateSession.user_id == current_user.id)
        .order_by(desc(DebateSession.updated_at))
    ).all()

    if not sessions:
        return []

    session_ids = [item.id for item in sessions]
    last_turns = db.scalars(
        select(DebateTurn)
        .where(DebateTurn.session_id.in_(session_ids))
        .order_by(desc(DebateTurn.created_at))
    ).all()
    last_preview_by_session: dict[int, str] = {}
    for turn in last_turns:
        if turn.session_id in last_preview_by_session:
            continue
        preview = (turn.content or "").strip().replace("\n", " ")
        last_preview_by_session[turn.session_id] = preview[:140]

    return [
        DebateSessionSummaryOut(
            id=item.id,
            topic=item.topic,
            status=item.status,  # type: ignore[arg-type]
            stage=item.stage,  # type: ignore[arg-type]
            updated_at=item.updated_at,
            last_turn_preview=last_preview_by_session.get(item.id, ""),
        )
        for item in sessions
    ]


@router.post("/sessions", response_model=DebateSessionDetailOut)
def create_debate_session(
    payload: DebateSessionCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty")

    _ensure_model_enabled(payload.pro_model_id)
    _ensure_model_enabled(payload.con_model_id)
    if payload.judge_model_id:
        _ensure_model_enabled(payload.judge_model_id)

    session = DebateSession(
        user_id=current_user.id,
        topic=topic,
        status="created",
        stage="opening",
        config_json=DebateSessionConfig.from_create_payload(payload).to_json(),
    )
    db.add(session)
    db.flush()

    participants = [
        DebateParticipant(
            session_id=session.id,
            model_id=payload.pro_model_id,
            side="pro",
            style=payload.style,
            order_index=0,
        ),
        DebateParticipant(
            session_id=session.id,
            model_id=payload.con_model_id,
            side="con",
            style=payload.style,
            order_index=1,
        ),
    ]
    db.add_all(participants)
    db.commit()
    loaded = load_debate_session_for_user(db=db, session_id=session.id, user_id=current_user.id)
    return build_debate_session_detail(loaded)


@router.get("/sessions/{session_id}", response_model=DebateSessionDetailOut)
async def get_debate_session(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    session = load_debate_session_for_user(db=db, session_id=session_id, user_id=current_user.id)
    return build_debate_session_detail(
        session,
        active_run=await _debate_active_run_payload(request, session.id),
    )


@router.patch("/sessions/{session_id}", response_model=DebateSessionSummaryOut)
def update_debate_session(
    session_id: int,
    payload: DebateSessionUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    session = db.scalar(
        select(DebateSession).where(DebateSession.id == session_id, DebateSession.user_id == current_user.id)
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Debate session not found")

    next_topic = payload.topic.strip()
    if not next_topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty")

    session.topic = next_topic
    db.add(session)
    db.commit()
    db.refresh(session)

    last_turn = db.scalar(
        select(DebateTurn)
        .where(DebateTurn.session_id == session.id)
        .order_by(desc(DebateTurn.created_at))
    )
    preview = ((last_turn.content if last_turn else "") or "").strip().replace("\n", " ")[:140]

    return DebateSessionSummaryOut(
        id=session.id,
        topic=session.topic,
        status=session.status,  # type: ignore[arg-type]
        stage=session.stage,  # type: ignore[arg-type]
        updated_at=session.updated_at,
        last_turn_preview=preview,
    )


@router.delete("/sessions/{session_id}", status_code=204)
def delete_debate_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    session = load_debate_session_for_user(db=db, session_id=session_id, user_id=current_user.id)

    for turn in session.turns:
        if turn.target_turn_id is not None:
            turn.target_turn_id = None
            db.add(turn)

    db.flush()
    db.delete(session)
    db.commit()


@router.post("/sessions/{session_id}/next")
async def advance_debate_session(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    session = load_debate_session_for_user(db=db, session_id=session_id, user_id=current_user.id)
    return await advance_debate_session_response(
        db=db,
        request=request,
        session=session,
    )


@router.post("/sessions/{session_id}/judge/ask")
async def ask_debate_judge_question(
    session_id: int,
    payload: DebateJudgeAskIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    session = load_debate_session_for_user(db=db, session_id=session_id, user_id=current_user.id)
    return await ask_debate_judge_question_response(
        db=db,
        request=request,
        session=session,
        payload=payload,
    )


@router.post("/sessions/{session_id}/judge/decision")
async def create_debate_judge_decision(
    session_id: int,
    payload: DebateJudgeDecisionIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    session = load_debate_session_for_user(db=db, session_id=session_id, user_id=current_user.id)
    return await create_debate_judge_decision_response(
        db=db,
        request=request,
        session=session,
        payload=payload,
    )


@router.get("/sessions/{session_id}/stream/active")
async def stream_active_debate_run(
    session_id: int,
    request: Request,
    run_id: Optional[str] = Query(default=None),
    after_seq: Optional[int] = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    session = load_debate_session_for_user(db=db, session_id=session_id, user_id=current_user.id)
    active_run = await _debate_active_run_payload(request, session.id)
    if active_run is None:
        raise HTTPException(status_code=404, detail="No active debate run")
    current_run_id = active_run.get("run_id")
    if run_id and isinstance(current_run_id, str) and current_run_id != run_id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ActiveRunMismatch",
                "message": "Active debate run changed. Refresh the session and reconnect.",
            },
        )
    return await stream_active_debate_session_response(
        request=request,
        session=session,
        after_seq=after_seq,
    )
