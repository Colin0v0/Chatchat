from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

logger = logging.getLogger("chatchat.debate")

from ..core.config import settings
from ..llm import stream_chat
from ..schemas import (
    DebateFreeDebateStateOut,
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
DEFAULT_FREE_DEBATE_BUDGET_MS = 60_000
DEFAULT_STAGE_TURN_BUDGET_MS = {
    "opening": 10_000,
    "rebuttal": 10_000,
    "closing": 15_000,
    "judge_decision": 10_000,
}
FREE_DEBATE_MIN_START_MS = 5_000
SIDE_LABEL = {"pro": "正方", "con": "反方"}
STAGE_LABEL = {
    "opening": "立论",
    "rebuttal": "驳论",
    "free_debate": "自由辩论",
    "closing": "总结陈词",
    "judge_decision": "裁决",
}
SCORE_DIMENSION_KEYS = (
    "argument_strength",
    "response_quality",
    "comparison_ability",
    "time_control",
)
JUDGE_STAGE_SCORE_KEYS = ("opening", "rebuttal", "free_debate", "closing")
JUDGE_STAGE_SCORE_LABELS = {
    "opening": "立论",
    "rebuttal": "驳论",
    "free_debate": "自由辩论",
    "closing": "总结陈词",
}
JUDGE_COMMON_ISSUES = (
    "循环论证",
    "偏离主题",
    "偷换概念",
    "没有回应对方核心点",
    "比较不足",
    "超时截断",
    "重复车轱辘话",
)
STAGE_TASK_HINT = {
    "opening": "把这场辩论的盘面先搭起来：先让裁判知道你方到底怎样判断这题，再顺势立住 2 到 3 个能支撑该判断的核心理由。",
    "rebuttal": "把对方刚成型的论证链条拆开：优先处理最影响胜负的那个 clash，抓前提、抓跳步、抓比较失衡，再把主动权抢回己方。",
    "free_debate": "以正式自由辩论的方式推进主战场：优先咬住刚刚那一下最关键的 clash，必要时直接卡定义、抓前提、逼比较、追承认。你不需要照模板背稿，只要清楚知道这轮要打哪一点、为什么这一点决定胜负。",
    "closing": "替裁判把胜负真正算出来：不要再沿着最后一句继续缠斗，而是把整场最关键的 2 到 3 个争点结算清楚，归纳我方主张为何成立，再自然升华到这场辩论真正留下的判断。",
    "judge_decision": "回应裁判追问，直接围绕问题作答。",
}


def _stage_role_hint(stage: str, side: str) -> str:
    if stage == "opening":
        if side == "pro":
            return "你是正方立论位，像搭框架的人：先把裁判看这题的入口握在手里，再让后续攻防都往你设定的标准里走。"
        return "你是反方立论位，像改盘面的人：你不只是说反对，而是要换掉正方想主导的看法，让裁判从一开始就看到另一套更有力的判断方式。"
    if stage == "rebuttal":
        return "你在驳论位，像拆链条的人：责任不是重讲己方稿子，而是抓住对方最像样的那条论证，拆它的前提、因果和比较，让它站不住。"
    if stage == "free_debate":
        return "你在自由辩论位：责任不是重新发表完整陈词，而是顺着场上最新交锋接招、追问、反压、转守为攻，让战场不断收束到最关键的胜负点。"
    if stage == "closing":
        return "你在总结位，像替裁判落判的人：责任是把散开的攻防压成可判的输赢图景，归纳我方已经打成的优势，告诉裁判最后该因为哪几个点判我方赢，而不是继续按自由辩节奏缠斗。"
    return "你需要直接回答裁判问题，并让裁判清楚知道哪一方更占优。"


def _stage_structure_hint(stage: str) -> str:
    if stage == "opening":
        return "可以自然展开，但最好先亮出立场与判断方式，再顺着推出核心理由。每个核心理由最好都带上观点、逻辑、类比/例子/数字和预置追问。重点是先把盘面立住，不必写成教科书提纲。"
    if stage == "rebuttal":
        return "最好先点名并回应对方上一轮最伤的一点，再集中拆 1 到 2 条关键链路；每一段都尽量完成观点、逻辑、类比/例子/数字、追问这四件事，最后把话收回到为什么这轮之后仍然是我方占优。"
    if stage == "free_debate":
        return "没有固定模板。通常先处理对方刚才最关键的一击或问题，再顺势推进你真正想打成的那一个点；需要时可以卡定义、抓矛盾、逼比较、追承认。可以短打，也可以连续压一步，但别摊太多平行战线。"
    if stage == "closing":
        return "建议先亮出最终判断和判准，再归纳我方已经打成的 2 到 3 个胜点，完成最终比较和结算，最后用一句有情绪张力但不空的升华收口。可以顺手点破对方误区，但不要再按自由辩节奏逐点追打。"
    return "建议结构：先直接回答问题，再给出最关键理由。"


def _stage_forbidden_hint(stage: str) -> str:
    if stage == "opening":
        return "不要一上来铺情绪、喊口号或讲长故事；也不要把立论写成僵硬提纲。要像真人立盘，不像在交作业。"
    if stage == "rebuttal":
        return "不要把驳论写成“我方立论重说一遍”，也不要平均回应所有枝节。驳论必须有对象感，像在拆对方，不像在自说自话，更不要空话、套话和抽象大词连发。"
    if stage == "free_debate":
        return "不要寒暄，不要背稿式重讲，不要每轮都像一篇完整小作文；也不要机械套模板、跑题翻旧账、跳过对方关键问题，或把自己上一轮的话换个说法再念一遍。自由辩可以短，也可以稍长，但必须像真实交锋。"
    if stage == "closing":
        return "不要提出新的独立论点、定义、机制或例子；不要把总结写成对对方最后一句的逐句反击，也不要再抛追问。更不要只顾抒情升维却不结算胜负。总结应该像结辩落判，不是把自由辩再打一遍。"
    return "不要回避问题，不要空泛表态。"


def _stage_hard_rules(stage: str) -> list[str]:
    common_rules = [
        "硬规则：严禁空话、套话、哲学堆砌、抽象大词连发。要锋利、好懂、像赛场攻防，不像公众号鸡汤。",
        "硬规则：优先使用通俗比喻、具体场景、简单数字、小例子来压实论点，但这些材料必须服务当前战点。",
    ]

    if stage == "opening":
        return [
            "硬规则：开篇要先立清楚我方立场和判断标准，再展开核心理由，不要一上来散点铺陈。",
            "硬规则：整体上要让裁判听出观点、逻辑、类比/例子/数字，必要时可以顺手埋比较或追问，但不必为了凑格式写成僵硬模板。",
            *common_rules,
        ]

    if stage == "rebuttal":
        return [
            "硬规则：优先处理对方上一轮最影响胜负的一击，不平均回应所有枝节，不跑题，不翻旧账。",
            "硬规则：如果对方或裁判上一轮抛了明确问题，要先正面回应，再继续拆链条或反打。",
            "硬规则：整体上要让裁判听出观点、逻辑、类比/例子/数字和推进动作，但不要求每一段都完全同构。",
            *common_rules,
        ]

    if stage == "free_debate":
        return [
            "硬规则：除首轮开篇还没有对方发言可回时以外，只针对对方上一轮最关键的一击或问题回应和攻击，不跑题，不翻旧账，不重复自己刚讲过的句式。",
            "硬规则：优先抓定义、前提、比较标准、因果跳步、对方无法承认的代价这几类真正决定胜负的点，不要把自由辩打成素材堆砌。",
            "硬规则：如果对方或裁判上一轮抛了明确问题，原则上先正面回答，再决定要不要追问或反压；别跳过关键问题直接另起炉灶。",
            "硬规则：要让裁判听出你在推进，而不是原地重复。推进方式可以是回应、设限、逼比较、逼承认、转守为攻，不要求固定句式。",
            "硬规则：严禁空话、套话、哲学堆砌、抽象大词连发。要锋利、好懂、像赛场攻防，不像公众号鸡汤。",
            "硬规则：优先使用通俗比喻、具体场景、简单数字、小例子来压实论点，但这些材料必须服务当前战点。",
        ]

    if stage == "closing":
        return [
            "硬规则：总结不要再按自由辩节奏逐句缠斗，也不要再抛新的追问；重点是把我方已经打成的优势收束成最终胜点。",
            "硬规则：请归纳 2 到 3 个最能决定胜负的理由，讲清比较标准、胜负结算和为什么这些点足以判我方赢。",
            "硬规则：可以简短提到对方失误，但只能作为比较背景，不能把总结写成继续攻击对方的逐点反击。",
            "硬规则：最后允许有一点情怀和升维，但必须建立在前面已经讲清的胜点和比较上，像收口，不像另开新战场。",
            *common_rules,
        ]

    return [
        "硬规则：先正面回答裁判问题，再给出最关键理由，不要回避。",
        *common_rules,
    ]


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


def _turn_meta(turn: DebateTurn) -> dict[str, Any]:
    payload = _safe_json_loads(turn.sources_json, {})
    return payload if isinstance(payload, dict) else {}


def _set_turn_meta(turn: DebateTurn, **updates: Any) -> dict[str, Any]:
    payload = _turn_meta(turn)
    payload.update(updates)
    turn.sources_json = json.dumps(payload, ensure_ascii=False)
    return payload


def _turn_payload(turn: DebateTurn) -> DebateTurnOut:
    meta = _turn_meta(turn)
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
        elapsed_ms=_to_int(meta.get("elapsed_ms"), 0) or None,
        truncated=_to_bool(meta.get("truncated"), False),
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
        free_debate_enabled=_free_debate_enabled(session),
        free_debate_state=_free_debate_clock_payload(session),
        stage_time_limits_ms=_stage_time_limits_ms(session),
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


def _save_config(session: DebateSession, payload: dict[str, Any]) -> None:
    session.config_json = json.dumps(payload, ensure_ascii=False)


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _score_to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        text = (
            str(value)
            .strip()
            .replace("%", "")
            .replace("分", "")
            .replace("：", ":")
            .replace("，", ",")
        )
        score = int(float(text))
        return max(0, min(100, score))
    except (ValueError, TypeError):
        return None


def _free_debate_enabled(session: DebateSession) -> bool:
    return True


def _stage_time_limits_ms(session: DebateSession) -> dict[str, int]:
    config = _config(session)
    return {
        "opening": max(1_000, _to_int(config.get("opening_budget_ms"), DEFAULT_STAGE_TURN_BUDGET_MS["opening"])),
        "rebuttal": max(1_000, _to_int(config.get("rebuttal_budget_ms"), DEFAULT_STAGE_TURN_BUDGET_MS["rebuttal"])),
        "free_debate": max(1_000, _to_int(config.get("free_debate_budget_ms"), DEFAULT_FREE_DEBATE_BUDGET_MS)),
        "closing": max(1_000, _to_int(config.get("closing_budget_ms"), DEFAULT_STAGE_TURN_BUDGET_MS["closing"])),
    }


def _stage_turn_budget_ms(session: DebateSession, stage: str) -> int | None:
    if stage == "judge_decision":
        return DEFAULT_STAGE_TURN_BUDGET_MS["judge_decision"]
    return _stage_time_limits_ms(session).get(stage)


def _stage_target_seconds(session: DebateSession, stage: str) -> int | None:
    budget_ms = _stage_turn_budget_ms(session, stage)
    if budget_ms is None:
        return None
    return max(1, int(round((budget_ms / 1000) * 0.8)))


def _free_debate_budget_ms(session: DebateSession) -> int:
    return _stage_time_limits_ms(session)["free_debate"]


def _default_free_debate_state(session: DebateSession) -> dict[str, Any]:
    budget_ms = _free_debate_budget_ms(session)
    return {
        "pro_remaining_ms": budget_ms,
        "con_remaining_ms": budget_ms,
        "active_side": None,
        "active_turn_id": None,
        "active_turn_started_at": None,
        "turn_count": len(_speaker_turns(session, stage="free_debate")),
        "ended_reason": None,
    }


def _free_debate_state(session: DebateSession) -> dict[str, Any] | None:
    if not _free_debate_enabled(session):
        return None

    payload = _config(session)
    state = payload.get("free_debate_state")
    if not isinstance(state, dict):
        state = _default_free_debate_state(session)
    budget_ms = _free_debate_budget_ms(session)
    return {
        "pro_remaining_ms": max(0, _to_int(state.get("pro_remaining_ms"), budget_ms)),
        "con_remaining_ms": max(0, _to_int(state.get("con_remaining_ms"), budget_ms)),
        "active_side": state.get("active_side") if state.get("active_side") in {"pro", "con"} else None,
        "active_turn_id": _to_int(state.get("active_turn_id"), 0) or None,
        "active_turn_started_at": str(state.get("active_turn_started_at")).strip()
        if state.get("active_turn_started_at")
        else None,
        "turn_count": max(0, _to_int(state.get("turn_count"), len(_speaker_turns(session, stage="free_debate")))),
        "ended_reason": state.get("ended_reason")
        if state.get("ended_reason") in {"pro_timeout", "con_timeout", "both_timeout", "manual"}
        else None,
    }


def _save_free_debate_state(session: DebateSession, state: dict[str, Any]) -> dict[str, Any]:
    payload = _config(session)
    payload["free_debate_state"] = {
        "pro_remaining_ms": max(0, _to_int(state.get("pro_remaining_ms"), _free_debate_budget_ms(session))),
        "con_remaining_ms": max(0, _to_int(state.get("con_remaining_ms"), _free_debate_budget_ms(session))),
        "active_side": state.get("active_side") if state.get("active_side") in {"pro", "con"} else None,
        "active_turn_id": _to_int(state.get("active_turn_id"), 0) or None,
        "active_turn_started_at": str(state.get("active_turn_started_at")).strip()
        if state.get("active_turn_started_at")
        else None,
        "turn_count": max(0, _to_int(state.get("turn_count"), 0)),
        "ended_reason": state.get("ended_reason")
        if state.get("ended_reason") in {"pro_timeout", "con_timeout", "both_timeout", "manual"}
        else None,
    }
    _save_config(session, payload)
    return payload["free_debate_state"]


def _ensure_free_debate_state(session: DebateSession) -> dict[str, Any] | None:
    state = _free_debate_state(session)
    if state is None:
        return None
    return _save_free_debate_state(session, state)


def _stage_sequence(session: DebateSession) -> tuple[str, ...]:
    sequence = ["opening", "rebuttal"]
    if _free_debate_enabled(session):
        sequence.append("free_debate")
    sequence.append("closing")
    return tuple(sequence)


def _next_stage(session: DebateSession, stage: str) -> str:
    sequence = _stage_sequence(session)
    try:
        index = sequence.index(stage)
    except ValueError:
        return "judge_decision"
    if index >= len(sequence) - 1:
        return "judge_decision"
    return sequence[index + 1]


def _free_debate_clock_payload(session: DebateSession) -> DebateFreeDebateStateOut | None:
    state = _free_debate_state(session)
    if state is None:
        return None
    return DebateFreeDebateStateOut(
        pro_remaining_ms=state["pro_remaining_ms"],
        con_remaining_ms=state["con_remaining_ms"],
        active_side=state["active_side"],
        active_turn_id=state["active_turn_id"],
        active_turn_started_at=state["active_turn_started_at"],
        turn_count=state["turn_count"],
        ended_reason=state["ended_reason"],
    )


def _free_debate_clock_event_line(session: DebateSession) -> str | None:
    payload = _free_debate_clock_payload(session)
    if payload is None:
        return None
    return json.dumps(
        {
            "type": "free_debate_clock",
            "state": payload.model_dump(mode="json"),
        },
        ensure_ascii=False,
    ) + "\n"


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


def _recent_opponent_turns_text(session: DebateSession, side: str, limit: int = 2) -> str:
    opponent = "con" if side == "pro" else "pro"
    turns = _speaker_turns(session, side=opponent)[-limit:]
    if not turns:
        return "暂无。"
    return "\n".join(f"- {turn.content.strip()}" for turn in turns if turn.content.strip())


def _next_free_debate_side(session: DebateSession) -> str:
    turns = _speaker_turns(session, stage="free_debate")
    if not turns:
        return "pro"
    last_turn = turns[-1]
    participant = next((item for item in session.participants if item.id == last_turn.speaker_participant_id), None)
    last_side = participant.side if participant else "pro"
    return "con" if last_side == "pro" else "pro"


def _mark_free_debate_ended(session: DebateSession, state: dict[str, Any]) -> dict[str, Any]:
    pro_out = state["pro_remaining_ms"] <= 0
    con_out = state["con_remaining_ms"] <= 0
    if pro_out and con_out:
        state["ended_reason"] = "both_timeout"
    elif pro_out:
        state["ended_reason"] = "pro_timeout"
    elif con_out:
        state["ended_reason"] = "con_timeout"
    return state


def _is_free_debate_over(session: DebateSession, state: dict[str, Any] | None = None) -> bool:
    next_state = state or _free_debate_state(session)
    if next_state is None:
        return False
    if next_state["pro_remaining_ms"] <= 0 or next_state["con_remaining_ms"] <= 0:
        _save_free_debate_state(session, _mark_free_debate_ended(session, next_state))
        return True
    next_side = _next_free_debate_side(session)
    remaining_key = "pro_remaining_ms" if next_side == "pro" else "con_remaining_ms"
    if int(next_state.get(remaining_key, 0)) <= FREE_DEBATE_MIN_START_MS:
        _save_free_debate_state(session, next_state)
        return True
    return False


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
        suffix = " [超时截断]" if _to_bool(_turn_meta(turn).get("truncated"), False) else ""
        lines.append(f"[{STAGE_LABEL.get(turn.stage, turn.stage)}][{side_label}][{model_label}] {turn.content}{suffix}")
    return "\n".join(lines).strip()


def _dimension_scores_from_payload(*sources: Any) -> dict[str, dict[str, int | None]]:
    def _pair_from_entry(entry: Any) -> dict[str, int | None] | None:
        if not isinstance(entry, dict):
            return None
        pro = _score_to_int(entry.get("pro") or entry.get("正方"))
        con = _score_to_int(entry.get("con") or entry.get("反方"))
        return {
            "pro": min(25, pro) if pro is not None else None,
            "con": min(25, con) if con is not None else None,
        }

    dimensions: dict[str, dict[str, int | None]] = {}
    for key in SCORE_DIMENSION_KEYS:
        pair: dict[str, int | None] | None = None
        for source in sources:
            if not isinstance(source, dict):
                continue
            nested = source.get("dimensions")
            if isinstance(nested, dict) and key in nested:
                pair = _pair_from_entry(nested.get(key))
                if pair is not None:
                    break
            if key in source:
                pair = _pair_from_entry(source.get(key))
                if pair is not None:
                    break
        if pair is not None and (pair["pro"] is not None or pair["con"] is not None):
            dimensions[key] = pair
    return dimensions


def _stage_score_pair_from_entry(entry: Any) -> dict[str, int | None] | None:
    if not isinstance(entry, dict):
        return None
    pro = _score_to_int(entry.get("pro") or entry.get("正方"))
    con = _score_to_int(entry.get("con") or entry.get("反方"))
    return {
        "pro": min(25, pro) if pro is not None else None,
        "con": min(25, con) if con is not None else None,
    }


def _stage_scores_from_payload(*sources: Any) -> dict[str, dict[str, int | None]]:
    normalized: dict[str, dict[str, int | None]] = {}
    alias_to_stage = {
        "opening": "opening",
        "立论": "opening",
        "rebuttal": "rebuttal",
        "驳论": "rebuttal",
        "free_debate": "free_debate",
        "自由辩论": "free_debate",
        "free debate": "free_debate",
        "closing": "closing",
        "总结": "closing",
        "结辩": "closing",
    }

    for key in JUDGE_STAGE_SCORE_KEYS:
        pair: dict[str, int | None] | None = None
        for source in sources:
            if not isinstance(source, dict):
                continue
            nested = source.get("stage_scores")
            candidate_source = nested if isinstance(nested, dict) else source
            for candidate_key, candidate_value in candidate_source.items():
                mapped = alias_to_stage.get(str(candidate_key).strip().lower())
                if mapped != key:
                    continue
                pair = _stage_score_pair_from_entry(candidate_value)
                if pair is not None:
                    break
            if pair is not None:
                break
        if pair is not None and (pair["pro"] is not None or pair["con"] is not None):
            normalized[key] = pair
    return normalized


def _normalize_issue_list(value: Any) -> list[str]:
    if isinstance(value, str):
        items = re.split(r"[、,，/；;\n]+", value)
    elif isinstance(value, list):
        items = [str(item) for item in value]
    else:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _issues_from_payload(*sources: Any) -> dict[str, list[str]]:
    result = {"pro": [], "con": [], "shared": []}
    alias_to_side = {
        "pro": "pro",
        "正方": "pro",
        "con": "con",
        "反方": "con",
        "shared": "shared",
        "双方": "shared",
        "common": "shared",
    }

    for source in sources:
        if not isinstance(source, dict):
            continue
        nested = source.get("issues")
        candidate_source = nested if isinstance(nested, dict) else {}
        for candidate_key, candidate_value in candidate_source.items():
            mapped = alias_to_side.get(str(candidate_key).strip().lower())
            if not mapped:
                mapped = alias_to_side.get(str(candidate_key).strip())
            if not mapped:
                continue
            normalized = _normalize_issue_list(candidate_value)
            if normalized:
                result[mapped] = normalized
        for side in result:
            if result[side]:
                continue
            normalized = _normalize_issue_list(source.get(side))
            if normalized:
                result[side] = normalized
    return result


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _analysis_from_payload(*sources: Any) -> dict[str, str]:
    result = {
        "pro_review": "",
        "con_review": "",
        "shared_feedback": "",
        "key_decision": "",
        "final_vote": "",
    }

    for source in sources:
        if not isinstance(source, dict):
            continue
        nested = source.get("analysis")
        candidate_source = nested if isinstance(nested, dict) else source
        result["pro_review"] = _first_text(
            result["pro_review"],
            candidate_source.get("pro_review"),
            candidate_source.get("pro"),
            candidate_source.get("正方评价"),
        )
        result["con_review"] = _first_text(
            result["con_review"],
            candidate_source.get("con_review"),
            candidate_source.get("con"),
            candidate_source.get("反方评价"),
        )
        result["shared_feedback"] = _first_text(
            result["shared_feedback"],
            candidate_source.get("shared_feedback"),
            candidate_source.get("both"),
            candidate_source.get("双方共同表现"),
        )
        result["key_decision"] = _first_text(
            result["key_decision"],
            candidate_source.get("key_decision"),
            candidate_source.get("key_point"),
            candidate_source.get("关键胜负手"),
        )
        result["final_vote"] = _first_text(
            result["final_vote"],
            candidate_source.get("final_vote"),
            candidate_source.get("vote"),
            candidate_source.get("最终投票"),
        )

    return result


def _own_key_points(session: DebateSession, side: str, limit: int = 2) -> str:
    turns = _speaker_turns(session, side=side)[-limit:]
    if not turns:
        return "暂无。"
    return "\n".join(f"- {turn.content.strip()}" for turn in turns if turn.content.strip())


def _recent_own_turns_text(session: DebateSession, side: str, limit: int = 2) -> str:
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
    side = participant.side
    side_style_key = "pro_style" if side == "pro" else "con_style"
    style = (
        str(session_config.get(side_style_key, "")).strip()
        or str(session_config.get("style", "")).strip()
        or "理性清晰"
    )
    opponent_last_turn = _latest_opponent_turn(session, side)
    latest_judge_turn = _latest_judge_question(session)
    latest_question = judge_question or (latest_judge_turn.content if latest_judge_turn else "")
    transcript = _recent_transcript(
        session,
        limit=12 if stage == "closing" else 10 if stage == "free_debate" else 6,
    )
    own_points = _own_key_points(session, side, limit=3 if stage == "closing" else 2)
    recent_own_turns = _recent_own_turns_text(session, side, limit=2)
    stage_task = STAGE_TASK_HINT.get(stage, STAGE_TASK_HINT["judge_decision"])
    role_hint = _stage_role_hint(stage, side)
    structure_hint = _stage_structure_hint(stage)
    forbidden_hint = _stage_forbidden_hint(stage)
    hard_rules = _stage_hard_rules(stage)
    opponent_reference = opponent_last_turn.content if opponent_last_turn else "暂无。"
    stage_persona_hint = {
        "opening": "这轮的气质应该像立论建盘：稳、准、先立标准再推理由。",
        "rebuttal": "这轮的气质应该像驳论拆解：盯住对方关键链条下刀，给裁判明确看到哪里断了。",
        "free_debate": "这轮的气质应该像自由辩压战点：紧、快、有来有回，始终贴着最新交锋推进。",
        "closing": "这轮的气质应该像结辩收口：把零散攻防压成最终胜点，让裁判顺着你的比较自然落判。",
        "judge_decision": "这轮的气质应该像最后答辩：直接、明确、围绕问题。",
    }.get(stage, "")
    stage_output_hint = {
        "opening": "这轮先把立场和判断方式说稳，再推进核心理由；要像在立盘，不像在列提纲。",
        "rebuttal": "这轮直接抓对方最值得拆的一两处下手，不要平均回应所有点。",
        "closing": "这轮要像赛场上的正式总结陈词：归纳我方胜点，做最终比较和落判，再顺势升华，不要继续逐句缠斗。",
        "judge_decision": "这轮先正面答问题，再补最关键理由。",
    }.get(stage, "")
    time_hint = ""
    if stage == "free_debate":
        state = _free_debate_state(session)
        if state is not None:
            remaining_ms = state["pro_remaining_ms"] if side == "pro" else state["con_remaining_ms"]
            time_hint = (
                f"你当前剩余总时长约 {remaining_ms / 1000:.1f} 秒，包含思考和输出。"
                "这不是单次发言时长上限，而是本方自由辩论总时长；你可以自行分配每次发言长短，系统只会持续扣减总时间。"
            )
        opponent_reference = _recent_opponent_turns_text(session, side, limit=1)
    else:
        limit_ms = _stage_turn_budget_ms(session, stage)
        target_seconds = _stage_target_seconds(session, stage)
        if limit_ms is not None and target_seconds is not None:
            time_hint = (
                f"本轮从开始思考到输出结束，最晚必须在 {limit_ms / 1000:.0f} 秒内结束。"
                f"你最好在 {target_seconds} 秒内完成主要输出，给网络和流式传输留出缓冲。"
                "如果感觉说不完，就立刻收束，不要拖到最后。超时会被系统直接截断。"
            )
    system_prompt = "\n".join(
        [
            f"你是本场辩论的{SIDE_LABEL.get(side, side)}辩手，使用模型标识为 {participant.model_id}。",
            f"你的发言风格：{style}。这是一条高优先级风格约束，但表达仍要像赛场陈词，不要像提示词复述。",
            f"辩题：{session.topic}",
            f"你的立场：始终坚持{SIDE_LABEL.get(side, side)}，不能倒戈。",
            f"当前阶段：{STAGE_LABEL.get(stage, stage)}。",
            role_hint,
            stage_persona_hint,
            f"这轮你要完成的事：{stage_task}",
            f"表达把握：{structure_hint}",
            f"底线约束：{forbidden_hint}",
            time_hint,
            "请模仿正式华语辩论赛陈词，而不是聊天、散文、作文、会议纪要或提示词复述。",
            "允许自然口语化，但必须紧凑、能判、能听出攻防目的，不要空转。",
            "直接进入正文，不要大段铺垫，不要客套开场，不要重复同一句意思。",
            "非自由辩阶段要明显收束篇幅：立论与驳论说到点上就停，总结要更像结辩而不是长篇复盘。",
            "不要输出任何身份前缀、括号标签、舞台动作或系统痕迹，例如“（正方）”“（Con）”“（裁决结果为 con）”“（拍桌）”“尊敬的裁判，各位好）”等。",
            "默认面向裁判发言，但语言要像赛场陈词，不要像写说明书。",
            *hard_rules,
            (
                "自由辩论特别规则：你这一轮必须正面回应对方刚才最新一击，不能完全无视场上最新交锋。"
                if stage == "free_debate"
                else ""
            ),
            (
                "自由辩论特别规则：允许你重复己方核心立场，但不能只是换个措辞原地踏步；你必须在回应、比较、追问、设限、逼承认之中至少完成一种有效推进。"
                if stage == "free_debate"
                else ""
            ),
            (
                "自由辩论特别规则：真实自由辩允许长短变化。你可以一句追击，也可以连续两三步压制，但要围绕同一主战点推进，不要一下子铺开多个平行论点。"
                if stage == "free_debate"
                else ""
            ),
            (
                "自由辩论特别规则：优先使用赛场上的推进方式，例如卡定义、抓矛盾、逼比较、逼承认、转守为攻、把对方论点压缩后再拆。"
                if stage == "free_debate"
                else ""
            ),
        ]
    )
    if stage == "free_debate":
        user_prompt = "\n\n".join(
            [
                f"你最近两轮自己说过的话：\n{recent_own_turns}",
                f"对方刚才最近的攻击：\n{opponent_reference}",
                f"裁判最新追问：\n{latest_question or '无'}",
                f"最近对话记录：\n{transcript or '暂无。'}",
                (
                    "请直接给出本轮自由辩论发言，从正文开始。"
                    "先处理眼前最关键的攻击、问题或定义争议，再顺势推进你真正要打成的那个点。"
                    "你可以短打，也可以顺势多压一步，但必须让裁判感觉到战场被你推进了。"
                    "不要求固定模板；需要时直接卡定义、抓前提、逼比较、追承认。"
                    "不要只是重复你最近两轮已经讲过的话；就算坚持同一核心立场，也要换成新的攻防动作。"
                ),
            ]
        )
    elif stage == "closing":
        user_prompt = "\n\n".join(
            [
                f"你方已讲过的关键点：\n{own_points}",
                f"对方最近核心内容：\n{opponent_reference}",
                f"裁判最新追问：\n{latest_question or '无'}",
                f"最近对话记录：\n{transcript or '暂无。'}",
                (
                    "请直接给出本轮总结陈词，从正文开始，不要解释你的策略。"
                    "不要再按自由辩节奏逐点缠斗，不要再抛新的追问。"
                    "请把我方已经打成的 2 到 3 个核心胜点归纳清楚，完成最后比较和结算，让裁判明确知道为什么该判我方赢。"
                    "若需要提到对方，只作为比较背景顺手带过。"
                    "结尾可以有一句有情绪、有格局的升华，但前提是前面的账已经算清楚。"
                    + (f" {stage_output_hint}" if stage_output_hint else "")
                ),
            ]
        )
    else:
        user_prompt = "\n\n".join(
            [
                f"你方已讲过的关键点：\n{own_points}",
                f"对方最近核心内容：\n{opponent_reference}",
                f"裁判最新追问：\n{latest_question or '无'}",
                f"最近对话记录：\n{transcript or '暂无。'}",
                (
                    "请直接给出本轮发言，从正文开始，不要解释你的策略。"
                    "如果对方或裁判刚刚抛了明确问题，请先直接回应，再继续推进。"
                    "每一段都尽量做到：有观点、有逻辑、有类比/例子/数字、有追问。"
                    + (f" {stage_output_hint}" if stage_output_hint else "")
                ),
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

        if session.stage == "free_debate":
            state = _ensure_free_debate_state(session)
            if state is not None and _is_free_debate_over(session, state):
                session.stage = _next_stage(session, "free_debate")
                session.status = "running" if session.stage != "judge_decision" else "waiting_judge"
                stage_changes.append(session.stage)
                continue
            return _participant_by_side(session, _next_free_debate_side(session)), stage_changes

        turns_in_stage = _speaker_turns(session, stage=session.stage)
        if len(turns_in_stage) < 2:
            side = "pro" if len(turns_in_stage) % 2 == 0 else "con"
            return _participant_by_side(session, side), stage_changes

        session.stage = _next_stage(session, session.stage)
        session.status = "running" if session.stage != "judge_decision" else "waiting_judge"
        if session.stage == "free_debate":
            _ensure_free_debate_state(session)
        stage_changes.append(session.stage)
        if session.stage == "judge_decision":
            return None, stage_changes


def _advance_after_generated_turn(session: DebateSession, completed_stage: str) -> list[str]:
    if completed_stage == "judge_decision":
        return []

    if completed_stage == "free_debate":
        state = _ensure_free_debate_state(session)
        if state is None or not _is_free_debate_over(session, state):
            return []
        session.stage = _next_stage(session, "free_debate")
        session.status = "running" if session.stage != "judge_decision" else "waiting_judge"
        return [session.stage]

    if len(_speaker_turns(session, stage=completed_stage)) < 2:
        return []

    session.stage = _next_stage(session, completed_stage)
    if session.stage == "judge_decision":
        session.status = "waiting_judge"
        return [session.stage]

    session.status = "running"
    if session.stage == "free_debate":
        _ensure_free_debate_state(session)
    return [session.stage]


def _winner_from_vote_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if "正方" in text or " pro" in f" {text} ":
        return "pro"
    if "反方" in text or " con" in f" {text} ":
        return "con"
    return ""


def _normalize_decision_scoring(
    *,
    winner_side: str | None = None,
    scoring_json: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    base = scoring_json if isinstance(scoring_json, dict) else {}
    normalized: dict[str, Any] = {**base}
    stage_scores = _stage_scores_from_payload(base)
    analysis = _analysis_from_payload(base)

    pro_score = _score_to_int(base.get("pro_score"))
    con_score = _score_to_int(base.get("con_score"))
    if stage_scores:
        pro_score = sum(value["pro"] or 0 for value in stage_scores.values())
        con_score = sum(value["con"] or 0 for value in stage_scores.values())
        normalized["stage_scores"] = stage_scores

    if pro_score is not None:
        normalized["pro_score"] = pro_score
    else:
        normalized.pop("pro_score", None)
    if con_score is not None:
        normalized["con_score"] = con_score
    else:
        normalized.pop("con_score", None)

    explicit_winner = winner_side if winner_side in {"pro", "con"} else ""
    vote_winner = _winner_from_vote_text(analysis.get("final_vote"))

    if pro_score is not None and con_score is not None and pro_score != con_score:
        resolved_winner = "pro" if pro_score > con_score else "con"
    else:
        resolved_winner = explicit_winner or vote_winner or "pro"

    if any(analysis.values()) or isinstance(base.get("analysis"), dict):
        analysis["final_vote"] = "本场我投正方一票" if resolved_winner == "pro" else "本场我投反方一票"
        normalized["analysis"] = analysis

    return resolved_winner, normalized


def _build_ai_evaluation_messages(
    session: DebateSession,
    *,
    commentary_markdown: str = "",
) -> list[ChatMessagePayload]:
    """让 AI 裁判模型对辩论打分并给出胜负建议，输出严格 JSON。"""
    transcript = _recent_transcript(session, limit=999)
    return [
        ChatMessagePayload(
            role="system",
            content=(
                "你是公正且严格遵守格式的辩论裁判。\n"
                "你必须只输出一行合法 JSON，不能输出 Markdown、解释、前后缀、代码块、项目符号或任何多余文字。\n"
                "输出字段必须严格等于以下 6 个键，键名不能变，不能新增字段：\n"
                '{"winner":"pro|con","pro_score":88,"con_score":82,"judge_comment":"这里写不超过80字的中文裁决摘要","analysis":{"pro_review":"...","con_review":"...","shared_feedback":"...","key_decision":"...","final_vote":"本场我投正方一票"},"stage_scores":{"opening":{"pro":22,"con":19},"rebuttal":{"pro":20,"con":21},"free_debate":{"pro":24,"con":22},"closing":{"pro":22,"con":20}},"issues":{"pro":["比较不足"],"con":["偏离主题"],"shared":["双方都有重复论述"]}}\n'
                "规则：\n"
                "1. winner 只能是 pro 或 con，禁止输出 draw 或平局，必须选出胜方。\n"
                "2. pro_score 和 con_score 必须是 0 到 100 的整数，不能是字符串，不能带百分号。\n"
                "3. stage_scores 必须包含四个阶段且只能包含四个阶段：opening、rebuttal、free_debate、closing，分别对应立论、驳论、自由辩、总结。\n"
                "4. 每个阶段都必须是 {\"pro\":整数,\"con\":整数}，分值范围 0 到 25。\n"
                "5. pro_score 必须等于四个阶段 pro 分之和；con_score 必须等于四个阶段 con 分之和。\n"
                "6. analysis 必须包含五个键：pro_review、con_review、shared_feedback、key_decision、final_vote。\n"
                "7. 在 pro_review 和 con_review 中，要同时写该方做得好的点、要改进的点，并自然融入明显成立的问题检测，例如循环论证、偏离主题、偷换概念、没有回应对方核心点、比较不足、超时截断、重复车轱辘话。不要为了凑标签硬写。\n"
                "8. shared_feedback 用来概括双方共同做得不错的地方，以及双方共同还可改进的地方。\n"
                "9. final_vote 必须是明确投票句，只能是“本场我投正方一票”或“本场我投反方一票”。\n"
                "10. issues 必须包含 pro、con、shared 三个数组，数组里只放明显成立的问题短语；若没有明显问题就返回空数组。\n"
                "11. 若辩论记录里出现[超时截断]，应在对应一方的评价和 issues 中体现，并在该阶段分数里合理扣分，但不必直接判负。\n"
                "12. judge_comment 必须是中文简短裁决摘要，不超过 80 字。\n"
                "13. 如果下面附带了“你刚刚已经给出的讲评”，JSON 裁决必须与该讲评保持一致：winner、judge_comment、analysis.final_vote 的倾向不能和讲评冲突，阶段分与总分也必须支持同一胜方。\n"
                "14. 即使证据不足，也必须给出完整六个字段。\n"
                "15. 你的回复如果不是上述 JSON，会被系统判定为无效。"
            ),
        ),
        ChatMessagePayload(
            role="user",
            content="\n\n".join(
                [
                    f"辩题：{session.topic}",
                    f"辩论记录：\n{transcript or '暂无'}",
                    f"你刚刚已经给出的讲评：\n{commentary_markdown or '暂无，请直接根据辩论记录完成一致的 JSON 裁决。'}",
                    f"常见问题检测参考：{ '、'.join(JUDGE_COMMON_ISSUES) }。",
                    "现在直接输出一行 JSON，不要解释，不要换行，不要代码块。",
                ]
            ),
        ),
    ]


def _build_ai_commentary_messages(session: DebateSession) -> list[ChatMessagePayload]:
    transcript = _recent_transcript(session, limit=999)
    return [
        ChatMessagePayload(
            role="system",
            content=(
                "你是这场辩论的资深中文辩论赛评委。\n"
                "请写一份像真人评委赛后讲评那样的 Markdown 点评，要求比一句短评更充分，但不要写成冗长论文。\n"
                "必须按下面的 6 个小标题输出，并保留标题原文：\n"
                "## 裁决摘要\n"
                "## 正方评价\n"
                "## 反方评价\n"
                "## 双方共同表现\n"
                "## 关键胜负手\n"
                "## 最终投票\n"
                "要求：\n"
                "1. 正方评价、反方评价都要同时写该方做得好的点和最需要改进的点。\n"
                "2. 如果存在循环论证、偏离主题、偷换概念、没有回应对方核心点、比较不足、超时截断、重复论述等问题，不要单独列清单，而要自然融进对应一方评价里。\n"
                "3. 双方共同表现要讲清这场交锋哪里打得好、哪里还停留在各说各话。\n"
                "4. 关键胜负手只讲真正决定比赛的一两个点。\n"
                "5. 最终投票必须明确写“本场我投正方一票”或“本场我投反方一票”。\n"
                "6. 全文要像评委讲评，信息量要足，不要太短，不要只写一句判断。"
            ),
        ),
        ChatMessagePayload(
            role="user",
            content="\n\n".join(
                [
                    f"辩题：{session.topic}",
                    f"辩论记录：\n{transcript or '暂无'}",
                    "请直接输出 Markdown 正文，不要输出代码块。",
                ]
            ),
        ),
    ]


def _parse_ai_evaluation(raw: str) -> dict | None:
    """从 AI 返回文本中提取 JSON 评分结果，失败返回 None。"""
    # 先尝试找 ```json...``` 或 ```...``` 代码块
    block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if block:
        raw = block.group(1)
    else:
        # 直接找第一个 { ... }
        obj = re.search(r"\{.*\}", raw, re.DOTALL)
        if obj:
            raw = obj.group(0)

    def _first_non_empty(*values: Any) -> Any:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
        return None

    def _normalize_winner(val: Any) -> str:
        text = str(val or "").strip().lower()
        mapping = {
            "pro": "pro",
            "正方": "pro",
            "正方胜": "pro",
            "pro side": "pro",
            "con": "con",
            "反方": "con",
            "反方胜": "con",
            "con side": "con",
        }
        return mapping.get(text, "")

    def _extract_from_text(text: str) -> dict[str, Any]:
        compact = text.strip()
        winner_match = re.search(
            r'(?:"winner"|"winner_side"|"winning_side"|获胜方|胜方)\s*[:：]\s*"?(pro|con|draw|正方胜|反方胜|平局|正方|反方)"?',
            compact,
            re.IGNORECASE,
        )
        pro_match = re.search(
            r'(?:"pro_score"|"proScore"|正方分)\s*[:：]\s*"?(100|[1-9]?\d(?:\.\d+)?)',
            compact,
            re.IGNORECASE,
        )
        con_match = re.search(
            r'(?:"con_score"|"conScore"|反方分)\s*[:：]\s*"?(100|[1-9]?\d(?:\.\d+)?)',
            compact,
            re.IGNORECASE,
        )
        comment_match = re.search(
            r'(?:"judge_comment"|"judgeComment"|"comment"|"reasoning"|裁决理由|点评)\s*[:：]\s*"([^"\n\r]+)"',
            compact,
            re.IGNORECASE,
        )
        return {
            "winner": winner_match.group(1) if winner_match else None,
            "pro_score": pro_match.group(1) if pro_match else None,
            "con_score": con_match.group(1) if con_match else None,
            "judge_comment": comment_match.group(1) if comment_match else None,
        }

    try:
        data = json.loads(raw)
    except Exception:
        data = _extract_from_text(raw)

    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    scoring = data.get("scoring_json") if isinstance(data.get("scoring_json"), dict) else {}
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    text_fallback = _extract_from_text(raw)

    winner = _normalize_winner(
        _first_non_empty(
            data.get("winner"),
            data.get("winner_side"),
            data.get("winning_side"),
            data.get("获胜方"),
            result.get("winner"),
            result.get("winner_side"),
            text_fallback.get("winner"),
        )
    )

    stage_scores = _stage_scores_from_payload(data, scoring, result)
    analysis = _analysis_from_payload(data, scoring, result)
    issues = _issues_from_payload(data, scoring, result)

    pro_score = _score_to_int(
        _first_non_empty(
            data.get("pro_score"),
            data.get("proScore"),
            data.get("正方分"),
            scores.get("pro"),
            scores.get("pro_score"),
            scoring.get("pro_score"),
            scoring.get("pro"),
            result.get("pro_score"),
            text_fallback.get("pro_score"),
        )
    )
    con_score = _score_to_int(
        _first_non_empty(
            data.get("con_score"),
            data.get("conScore"),
            data.get("反方分"),
            scores.get("con"),
            scores.get("con_score"),
            scoring.get("con_score"),
            scoring.get("con"),
            result.get("con_score"),
            text_fallback.get("con_score"),
        )
    )

    if stage_scores:
        pro_stage_total = sum(value["pro"] or 0 for value in stage_scores.values())
        con_stage_total = sum(value["con"] or 0 for value in stage_scores.values())
        if pro_score is None or pro_score != pro_stage_total:
            pro_score = pro_stage_total
        if con_score is None or con_score != con_stage_total:
            con_score = con_stage_total

    judge_comment = str(
        _first_non_empty(
            data.get("judge_comment"),
            data.get("judgeComment"),
            data.get("comment"),
            data.get("reasoning"),
            data.get("rationale"),
            data.get("裁决理由"),
            data.get("点评"),
            result.get("judge_comment"),
            result.get("comment"),
            text_fallback.get("judge_comment"),
        )
        or ""
    ).strip()

    if not judge_comment:
        judge_comment = _first_text(
            analysis.get("key_decision"),
            analysis.get("final_vote"),
        )[:80]

    scoring_json: dict[str, Any] = {}
    if pro_score is not None:
        scoring_json["pro_score"] = pro_score
    if con_score is not None:
        scoring_json["con_score"] = con_score
    if stage_scores:
        scoring_json["stage_scores"] = stage_scores
    if any(analysis.values()):
        scoring_json["analysis"] = analysis
    if any(issues.values()):
        scoring_json["issues"] = issues

    winner, scoring_json = _normalize_decision_scoring(winner_side=winner, scoring_json=scoring_json)

    return {
        "winner": winner,
        "pro_score": _score_to_int(scoring_json.get("pro_score")),
        "con_score": _score_to_int(scoring_json.get("con_score")),
        "judge_comment": judge_comment,
        "scoring_json": scoring_json,
    }


def _resolve_decision_winner_side(winner_side: str, scoring_json: dict[str, Any] | None = None) -> str:
    resolved_winner, _ = _normalize_decision_scoring(winner_side=winner_side, scoring_json=scoring_json)
    return resolved_winner


def _build_summary_messages(session: DebateSession) -> list[ChatMessagePayload]:
    transcript = _recent_transcript(session, limit=999)
    decision = session.judge_decision
    judge_note = decision.judge_comment if decision else ""
    winner = decision.winner_side if decision else "pro"
    winner_label = SIDE_LABEL.get(winner, "正方")
    return [
        ChatMessagePayload(
            role="system",
            content=(
                "你是辩论结辩摘要助手。\n"
                f"请站在胜方（{winner_label}）视角，基于整场辩论与裁判意见，写一段像真实结辩收口的摘要。\n"
                "结构固定，但语气不能像会议纪要、新闻概述或读书笔记；要像辩手在赛后把胜负说透。\n"
                "必须使用下面这个结构，不能改标题，不能加前言或结尾：\n"
                "为什么我方赢\n"
                "1. ...\n"
                "2. ...\n"
                "3. ...（若不足三点可省略）\n"
                "这场辩论说明了什么\n"
                "...\n"
                "要求：\n"
                "1. “为什么我方赢”部分只写 2 到 3 个最终胜点，每点都要像结辩里的胜负结算，而不是罗列过程。\n"
                "2. 多写比较和判准：说明为什么这些点足以决定胜负，而不只是说我方做了什么。\n"
                "3. 每个胜点最好都带上观点、逻辑、类比/例子/数字，让人一听就明白这分为什么算到我方头上。\n"
                "4. “这场辩论说明了什么”要从我方立场出发，收束成一段有格局的意义升华，可以顺带提到对方为何没能动摇这个判断，但不要把它写成继续攻击对方的清单。\n"
                "5. 语言要锋利、好懂，少空话，多比喻、场景、数字和例子，但都必须服务胜负判断。\n"
                "6. 结尾允许有一点情怀和升维，但必须建立在前面已经结算清楚的胜点上，像赛场结辩收口，不能凭空抒情。\n"
                "7. 不要复述全场，不要写成新闻总结，不要输出 Markdown 标题符号。"
            ),
        ),
        ChatMessagePayload(
            role="user",
            content="\n\n".join(
                [
                    f"辩题：{session.topic}",
                    f"裁决结果：{winner_label}获胜",
                    f"裁判评语：{judge_note or '无'}",
                    f"辩论记录：\n{transcript or '暂无'}",
                ]
            ),
        ),
    ]


__all__ = [
    "logger",
    "json",
    "datetime",
    "settings",
    "stream_chat",
    "Request",
    "Session",
    "DebateSession",
    "DebateParticipant",
    "DebateTurn",
    "DebateJudgeDecision",
    "DebateJudgeDecisionIn",
    "DebateJudgeAskIn",
    "_stage_turn_budget_ms",
    "strip_loose_think_tags",
    "_build_turn_messages",
    "_ensure_free_debate_state",
    "_free_debate_state",
    "_free_debate_clock_event_line",
    "_set_turn_meta",
    "_next_turn_index",
    "_save_free_debate_state",
    "_mark_free_debate_ended",
    "_advance_after_generated_turn",
    "_resolve_next_participant",
    "_participant_by_side",
    "_config",
    "_recent_transcript",
    "_decision_payload",
    "_build_ai_evaluation_messages",
    "_normalize_decision_scoring",
    "_parse_ai_evaluation",
    "_resolve_decision_winner_side",
    "_build_summary_messages",
    "build_debate_session_detail",
    "load_debate_session_for_user",
]
