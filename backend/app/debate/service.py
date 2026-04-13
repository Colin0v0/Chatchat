from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..core.config import settings
from ..llm import complete_chat, stream_chat
from ..schemas import (
    DebateJudgeDecisionIn,
    DebateJudgeDecisionOut,
    DebateJudgeAskIn,
    DebateParticipantOut,
    DebateSessionDetailOut,
    DebateTurnOut,
)
from ..storage.models import DebateJudgeDecision, DebateParticipant, DebateSession, DebateTurn
from ..chat.types import ChatMessagePayload

THINK_TAG_ONLY_PATTERN = re.compile(r"</?think>", re.IGNORECASE)
STAGE_SEQUENCE = ("opening", "rebuttal", "closing")
SIDE_LABEL = {"pro": "正方", "con": "反方"}
STAGE_LABEL = {
    "opening": "立论",
    "rebuttal": "驳论",
    "closing": "总结",
    "judge_decision": "裁决",
}
WORD_LIMIT_HINT = {
    "short": "控制在 100 到 150 字。",
    "standard": "控制在 200 到 300 字。",
    "deep": "控制在 400 到 600 字。",
}
STAGE_TASK_HINT = {
    "opening": "明确立场，定义关键概念，给出 2 到 3 个核心论据。",
    "rebuttal": "针对对方上一轮核心观点逐点反驳，避免重复立论。",
    "closing": "收束争点，强调己方最强理由，并回应最关键的攻击点。",
    "judge_decision": "回应裁判追问，直接围绕问题作答。",
}


def strip_loose_think_tags(content: str) -> str:
    if not content:
        return content
    return THINK_TAG_ONLY_PATTERN.sub("", content)


def _safe_json_loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return fallback
    return payload


def _summary_text(session: DebateSession) -> str:
    payload = _safe_json_loads(session.summary_json, {})
    if isinstance(payload, dict):
        return str(payload.get("content", "")).strip()
    return ""


def _decision_payload(decision: DebateJudgeDecision | None) -> DebateJudgeDecisionOut | None:
    if decision is None:
        return None
    scoring_json = _safe_json_loads(decision.scoring_json, {})
    if not isinstance(scoring_json, dict):
        scoring_json = {}
    return DebateJudgeDecisionOut(
        winner_side=decision.winner_side,  # type: ignore[arg-type]
        scoring_json=scoring_json,
        judge_comment=decision.judge_comment,
        created_at=decision.created_at,
    )


def _turn_payload(turn: DebateTurn) -> DebateTurnOut:
    return DebateTurnOut(
        id=turn.id,
        kind=turn.kind,
        stage=turn.stage,  # type: ignore[arg-type]
        turn_index=turn.turn_index,
        speaker_participant_id=turn.speaker_participant_id,
        target_turn_id=turn.target_turn_id,
        content=turn.content,
        reasoning=turn.reasoning_content,
        created_at=turn.created_at,
    )


def _ordered_turns(session: DebateSession) -> list[DebateTurn]:
    return sorted(
        session.turns,
        key=lambda turn: (
            turn.turn_index,
            turn.created_at.isoformat() if turn.created_at else "",
            turn.id,
        ),
    )


def build_debate_session_detail(session: DebateSession) -> DebateSessionDetailOut:
    return DebateSessionDetailOut(
        id=session.id,
        topic=session.topic,
        status=session.status,  # type: ignore[arg-type]
        stage=session.stage,  # type: ignore[arg-type]
        created_at=session.created_at,
        updated_at=session.updated_at,
        finished_at=session.finished_at,
        participants=[DebateParticipantOut.model_validate(item) for item in session.participants],
        turns=[_turn_payload(turn) for turn in _ordered_turns(session)],
        judge_decision=_decision_payload(session.judge_decision),
        summary=_summary_text(session),
    )


def load_debate_session_for_user(*, db: Session, session_id: int, user_id: int) -> DebateSession:
    session = db.scalar(
        select(DebateSession)
        .where(DebateSession.id == session_id, DebateSession.user_id == user_id)
        .options(
            selectinload(DebateSession.participants),
            selectinload(DebateSession.turns),
            selectinload(DebateSession.judge_decision),
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Debate session not found")
    return session


def _config(session: DebateSession) -> dict[str, Any]:
    payload = _safe_json_loads(session.config_json, {})
    return payload if isinstance(payload, dict) else {}


def _participant_by_side(session: DebateSession, side: str) -> DebateParticipant:
    for participant in session.participants:
        if participant.side == side:
            return participant
    raise HTTPException(status_code=400, detail=f"Debate participant not found for side: {side}")


def _speaker_turns(session: DebateSession, *, stage: str | None = None, side: str | None = None) -> list[DebateTurn]:
    turns = [turn for turn in _ordered_turns(session) if turn.kind == "speaker_turn"]
    if stage is not None:
        turns = [turn for turn in turns if turn.stage == stage]
    if side is not None:
        participant = _participant_by_side(session, side)
        turns = [turn for turn in turns if turn.speaker_participant_id == participant.id]
    return turns


def _next_turn_index(session: DebateSession) -> int:
    return (max((turn.turn_index for turn in session.turns), default=0) + 1)


def _latest_turn_for_side(session: DebateSession, side: str) -> DebateTurn | None:
    candidate_turns = _speaker_turns(session, side=side)
    return candidate_turns[-1] if candidate_turns else None


def _latest_opponent_turn(session: DebateSession, side: str) -> DebateTurn | None:
    return _latest_turn_for_side(session, "con" if side == "pro" else "pro")


def _latest_judge_question(session: DebateSession) -> DebateTurn | None:
    question_turns = [turn for turn in _ordered_turns(session) if turn.kind == "judge_question"]
    return question_turns[-1] if question_turns else None


def _recent_transcript(session: DebateSession, limit: int = 6) -> str:
    relevant_turns = [
        turn for turn in _ordered_turns(session) if turn.kind in {"speaker_turn", "judge_question"}
    ][-limit:]
    lines: list[str] = []
    for turn in relevant_turns:
        if turn.kind == "judge_question":
            lines.append(f"[裁判追问][{STAGE_LABEL.get(turn.stage, turn.stage)}] {turn.content}")
            continue
        speaker = next((item for item in session.participants if item.id == turn.speaker_participant_id), None)
        side_label = SIDE_LABEL.get(speaker.side if speaker else "", "辩手")
        model_label = speaker.model_id if speaker else "未知模型"
        lines.append(f"[{STAGE_LABEL.get(turn.stage, turn.stage)}][{side_label}][{model_label}] {turn.content}")
    return "\n".join(lines).strip()


def _own_key_points(session: DebateSession, side: str, limit: int = 2) -> str:
    turns = _speaker_turns(session, side=side)[-limit:]
    if not turns:
        return "暂无。"
    return "\n".join(f"- {turn.content.strip()}" for turn in turns if turn.content.strip())


def _build_turn_messages(
    *,
    session: DebateSession,
    participant: DebateParticipant,
    stage: str,
    judge_question: str | None = None,
) -> list[ChatMessagePayload]:
    session_config = _config(session)
    word_limit_level = str(session_config.get("word_limit_level", "standard")).strip() or "standard"
    style = str(session_config.get("style", "")).strip() or "理性清晰"
    side = participant.side
    opponent_last_turn = _latest_opponent_turn(session, side)
    latest_judge_turn = _latest_judge_question(session)
    latest_question = judge_question or (latest_judge_turn.content if latest_judge_turn else "")
    transcript = _recent_transcript(session)
    own_points = _own_key_points(session, side)
    stage_task = STAGE_TASK_HINT.get(stage, STAGE_TASK_HINT["judge_decision"])
    system_prompt = "\n".join(
        [
            f"你是本场辩论的{SIDE_LABEL.get(side, side)}辩手，使用模型标识为 {participant.model_id}。",
            f"辩题：{session.topic}",
            f"你的立场：始终坚持{SIDE_LABEL.get(side, side)}，不能倒戈。",
            f"当前阶段：{STAGE_LABEL.get(stage, stage)}。",
            f"风格要求：{style}。",
            f"任务要求：{stage_task}",
            WORD_LIMIT_HINT.get(word_limit_level, WORD_LIMIT_HINT["standard"]),
            "面向裁判发言，要回应对方，不要空泛重复，也不要输出列表编号以外的闲聊。",
        ]
    )
    user_prompt = "\n\n".join(
        [
            f"你方已讲过的关键点：\n{own_points}",
            f"对方上一轮核心内容：\n{opponent_last_turn.content if opponent_last_turn else '暂无。'}",
            f"裁判最新追问：\n{latest_question or '无'}",
            f"最近对话记录：\n{transcript or '暂无。'}",
            "请直接给出本轮发言。",
        ]
    )
    return [
        ChatMessagePayload(role="system", content=system_prompt),
        ChatMessagePayload(role="user", content=user_prompt),
    ]


def _resolve_next_participant(session: DebateSession) -> tuple[DebateParticipant | None, list[str]]:
    stage_changes: list[str] = []

    if session.status == "created":
        session.status = "running"

    while True:
        if session.stage == "judge_decision":
            session.status = "waiting_judge"
            return None, stage_changes

        turns_in_stage = _speaker_turns(session, stage=session.stage)
        if len(turns_in_stage) < 2:
            side = "pro" if len(turns_in_stage) == 0 else "con"
            return _participant_by_side(session, side), stage_changes

        current_index = STAGE_SEQUENCE.index(session.stage)
        if current_index == len(STAGE_SEQUENCE) - 1:
            session.stage = "judge_decision"
            session.status = "waiting_judge"
            stage_changes.append(session.stage)
            return None, stage_changes

        session.stage = STAGE_SEQUENCE[current_index + 1]
        session.status = "running"
        stage_changes.append(session.stage)


def _advance_after_generated_turn(session: DebateSession, completed_stage: str) -> list[str]:
    if completed_stage == "judge_decision":
        return []

    if len(_speaker_turns(session, stage=completed_stage)) < 2:
        return []

    current_index = STAGE_SEQUENCE.index(completed_stage)
    if current_index == len(STAGE_SEQUENCE) - 1:
        session.stage = "judge_decision"
        session.status = "waiting_judge"
        return [session.stage]

    session.stage = STAGE_SEQUENCE[current_index + 1]
    session.status = "running"
    return [session.stage]


async def _stream_speaker_turn(
    *,
    db: Session,
    session: DebateSession,
    participant: DebateParticipant,
    stage: str,
    target_turn_id: int | None = None,
    judge_question: str | None = None,
):
    prompt_messages = _build_turn_messages(
        session=session,
        participant=participant,
        stage=stage,
        judge_question=judge_question,
    )
    prompt_snapshot = "\n\n".join(message.content for message in prompt_messages)
    turn = DebateTurn(
        session=session,
        kind="speaker_turn",
        stage=stage,
        turn_index=_next_turn_index(session),
        speaker_participant_id=participant.id,
        target_turn_id=target_turn_id,
        prompt_snapshot=prompt_snapshot,
        content="",
    )
    session.updated_at = datetime.utcnow()
    db.add(turn)
    db.add(session)
    db.commit()
    db.refresh(turn)

    yield json.dumps(
        {
            "type": "meta",
            "turn": _turn_payload(turn).model_dump(mode="json"),
        },
        ensure_ascii=False,
    ) + "\n"

    answer_chunks: list[str] = []
    reasoning_chunks: list[str] = []
    async for chunk in stream_chat(model=participant.model_id, messages=prompt_messages):
        reasoning_delta = str(chunk.get("reasoning", {}).get("content", "") or "")
        if reasoning_delta:
            reasoning_chunks.append(reasoning_delta)
            yield json.dumps(
                {
                    "type": "reasoning",
                    "turn_id": turn.id,
                    "content": reasoning_delta,
                },
                ensure_ascii=False,
            ) + "\n"

        delta = strip_loose_think_tags(str(chunk.get("message", {}).get("content", "") or ""))
        if delta:
            answer_chunks.append(delta)
            yield json.dumps(
                {
                    "type": "token",
                    "turn_id": turn.id,
                    "content": delta,
                },
                ensure_ascii=False,
            ) + "\n"

    turn.content = "".join(answer_chunks).strip()
    turn.reasoning_content = "".join(reasoning_chunks).strip() or None
    session.updated_at = datetime.utcnow()
    db.add(turn)
    db.add(session)
    db.commit()
    db.refresh(turn)

    yield json.dumps(
        {
            "type": "turn_done",
            "turn": _turn_payload(turn).model_dump(mode="json"),
        },
        ensure_ascii=False,
    ) + "\n"


async def debate_next_event_stream(*, db: Session, request: Request, session: DebateSession):
    if session.status == "finished":
        yield json.dumps({"type": "error", "message": "Debate session already finished."}, ensure_ascii=False) + "\n"
        return

    participant, stage_changes = _resolve_next_participant(session)
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)

    for stage in stage_changes:
        yield json.dumps(
            {
                "type": "stage_changed",
                "stage": stage,
                "status": session.status,
            },
            ensure_ascii=False,
        ) + "\n"

    if participant is None:
        yield json.dumps(
            {
                "type": "done",
                "stage": session.stage,
                "status": session.status,
            },
            ensure_ascii=False,
        ) + "\n"
        return

    active_stage = session.stage
    async for event in _stream_speaker_turn(
        db=db,
        session=session,
        participant=participant,
        stage=active_stage,
        target_turn_id=_latest_opponent_turn(session, participant.side).id if _latest_opponent_turn(session, participant.side) else None,
    ):
        if await request.is_disconnected():
            return
        yield event

    stage_changes = _advance_after_generated_turn(session, active_stage)
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)

    for stage in stage_changes:
        yield json.dumps(
            {
                "type": "stage_changed",
                "stage": stage,
                "status": session.status,
            },
            ensure_ascii=False,
        ) + "\n"

    yield json.dumps(
        {
            "type": "done",
            "stage": session.stage,
            "status": session.status,
        },
        ensure_ascii=False,
    ) + "\n"


async def debate_ask_event_stream(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    payload: DebateJudgeAskIn,
):
    if session.status == "finished":
        yield json.dumps({"type": "error", "message": "Debate session already finished."}, ensure_ascii=False) + "\n"
        return

    if session.status == "created":
        session.status = "running"

    question_turn = DebateTurn(
        session=session,
        kind="judge_question",
        stage=session.stage,
        turn_index=_next_turn_index(session),
        prompt_snapshot="",
        content=payload.question.strip(),
    )
    session.updated_at = datetime.utcnow()
    db.add(question_turn)
    db.add(session)
    db.commit()
    db.refresh(question_turn)

    yield json.dumps(
        {
            "type": "judge_question",
            "turn": _turn_payload(question_turn).model_dump(mode="json"),
        },
        ensure_ascii=False,
    ) + "\n"

    target_sides = ("pro", "con") if payload.ask_to == "all" else (payload.ask_to,)
    previous_status = session.status

    for side in target_sides:
        participant = _participant_by_side(session, side)
        async for event in _stream_speaker_turn(
            db=db,
            session=session,
            participant=participant,
            stage=session.stage,
            target_turn_id=question_turn.id,
            judge_question=payload.question.strip(),
        ):
            if await request.is_disconnected():
                return
            yield event

    session.status = previous_status
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()
    db.refresh(session)

    yield json.dumps(
        {
            "type": "done",
            "stage": session.stage,
            "status": session.status,
        },
        ensure_ascii=False,
    ) + "\n"


async def _generate_summary(session: DebateSession) -> str:
    transcript = _recent_transcript(session, limit=10)
    decision = session.judge_decision
    judge_note = decision.judge_comment if decision else ""
    winner = decision.winner_side if decision else "draw"
    messages = [
        ChatMessagePayload(
            role="system",
            content=(
                "你是辩论总结助手。请基于辩论记录输出一段简洁中文总结，包含："
                "胜方、正方核心观点、反方核心观点、关键交锋点、裁判意见。"
            ),
        ),
        ChatMessagePayload(
            role="user",
            content="\n\n".join(
                [
                    f"辩题：{session.topic}",
                    f"裁决结果：{winner}",
                    f"裁判评语：{judge_note or '无'}",
                    f"辩论记录：\n{transcript or '暂无'}",
                ]
            ),
        ),
    ]
    try:
        return await complete_chat(model=settings.default_model, messages=messages)
    except Exception:
        winner_label = {"pro": "正方", "con": "反方", "draw": "平局"}.get(winner, "平局")
        return f"胜方：{winner_label}\n裁判评语：{judge_note or '无'}\n关键记录：\n{transcript or '暂无'}"


async def finalize_debate_decision(
    *,
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

    session = load_debate_session_for_user(db=db, session_id=session.id, user_id=session.user_id)
    summary = await _generate_summary(session)
    session.summary_json = json.dumps({"content": summary}, ensure_ascii=False)
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()

    return load_debate_session_for_user(db=db, session_id=session.id, user_id=session.user_id)
