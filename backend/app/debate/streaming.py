import asyncio
import json
import time
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.orm import Session

from ..core.config import settings
from ..llm import stream_chat
from ..schemas import DebateJudgeAskIn, DebateJudgeDecisionIn
from ..storage.models import DebateJudgeDecision, DebateParticipant, DebateSession, DebateTurn
from .common import (
    _advance_after_generated_turn,
    _build_ai_commentary_messages,
    _build_ai_evaluation_messages,
    _build_summary_messages,
    _build_turn_messages,
    _config,
    _decision_payload,
    _ensure_free_debate_state,
    _free_debate_clock_event_line,
    _free_debate_state,
    _is_free_debate_over,
    _latest_opponent_turn,
    _mark_free_debate_ended,
    _normalize_decision_scoring,
    _next_free_debate_side,
    _next_stage,
    _next_turn_index,
    _parse_ai_evaluation,
    _participant_by_side,
    _recent_transcript,
    _resolve_next_participant,
    _save_free_debate_state,
    _stage_turn_budget_ms,
    _set_turn_meta,
    _turn_payload,
    load_debate_session_for_user,
    logger,
    strip_loose_think_tags,
)

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
    free_debate_state = _ensure_free_debate_state(session) if stage == "free_debate" else None
    if free_debate_state is not None:
        time_budget_ms = (
            free_debate_state["pro_remaining_ms"]
            if participant.side == "pro"
            else free_debate_state["con_remaining_ms"]
        )
    else:
        time_budget_ms = _stage_turn_budget_ms(session, stage)
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
    if free_debate_state is not None:
        free_debate_state["active_side"] = participant.side
        free_debate_state["active_turn_started_at"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    session.updated_at = datetime.utcnow()
    db.add(turn)
    db.add(session)
    db.commit()
    db.refresh(turn)
    if free_debate_state is not None:
        free_debate_state["active_turn_id"] = turn.id
        _save_free_debate_state(session, free_debate_state)
        session.updated_at = datetime.utcnow()
        db.add(session)
        db.commit()
        db.refresh(session)
    # 刷新 session 的关联集合，确保后续 turn 能读到最新的 turns/participants
    db.refresh(session, attribute_names=["turns", "participants"])

    clock_event = _free_debate_clock_event_line(session)
    if clock_event:
        yield clock_event

    yield json.dumps(
        {
            "type": "meta",
            "turn": _turn_payload(turn).model_dump(mode="json"),
        },
        ensure_ascii=False,
    ) + "\n"

    answer_chunks: list[str] = []
    reasoning_chunks: list[str] = []
    turn_started = time.monotonic()
    truncated = False
    stream = stream_chat(model=participant.model_id, messages=prompt_messages)

    async def consume_stream() -> None:
        nonlocal truncated

        async for chunk in stream:
            elapsed_ms = int((time.monotonic() - turn_started) * 1000)
            if time_budget_ms is not None and elapsed_ms >= time_budget_ms:
                truncated = True
                break

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

            elapsed_ms = int((time.monotonic() - turn_started) * 1000)
            if time_budget_ms is not None and elapsed_ms >= time_budget_ms:
                truncated = True
                break

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

    try:
        if time_budget_ms is None:
            async for event in consume_stream():
                yield event
        else:
            iterator = consume_stream().__aiter__()
            while True:
                remaining_ms = time_budget_ms - int((time.monotonic() - turn_started) * 1000)
                if remaining_ms <= 0:
                    truncated = True
                    break
                try:
                    event = await asyncio.wait_for(iterator.__anext__(), timeout=remaining_ms / 1000)
                except StopAsyncIteration:
                    break
                yield event
    except asyncio.TimeoutError:
        truncated = True
    finally:
        aclose = getattr(stream, "aclose", None)
        if callable(aclose):
            try:
                await aclose()
            except Exception:
                logger.debug("debate stream close failed", exc_info=True)

    elapsed_ms = int((time.monotonic() - turn_started) * 1000)
    if time_budget_ms is not None:
        elapsed_ms = min(elapsed_ms, time_budget_ms)

    turn.content = "".join(answer_chunks).strip()
    turn.reasoning_content = "".join(reasoning_chunks).strip() or None
    _set_turn_meta(turn, elapsed_ms=elapsed_ms, truncated=truncated)
    if free_debate_state is not None:
        remaining_key = "pro_remaining_ms" if participant.side == "pro" else "con_remaining_ms"
        free_debate_state[remaining_key] = max(0, int(free_debate_state[remaining_key]) - elapsed_ms)
        free_debate_state["active_side"] = None
        free_debate_state["active_turn_id"] = None
        free_debate_state["active_turn_started_at"] = None
        free_debate_state["turn_count"] = int(free_debate_state.get("turn_count", 0)) + 1
        _save_free_debate_state(session, _mark_free_debate_ended(session, free_debate_state))
    session.updated_at = datetime.utcnow()
    db.add(turn)
    db.add(session)
    db.commit()
    db.refresh(turn)
    # 同步 session 关联，确保下一个 speaker 能读到本轮内容
    db.refresh(session, attribute_names=["turns", "participants"])

    yield json.dumps(
        {
            "type": "turn_done",
            "turn": _turn_payload(turn).model_dump(mode="json"),
        },
        ensure_ascii=False,
    ) + "\n"

    clock_event = _free_debate_clock_event_line(session)
    if clock_event:
        yield clock_event


async def _run_ai_evaluation(
    *, request: Request, session: DebateSession
):
    """先流式生成评委讲评，再生成结构化评分 JSON。"""
    session_config = _config(session)
    judge_model_id = str(session_config.get("judge_model_id", "")).strip()
    if not judge_model_id:
        judge_model_id = settings.default_model or ""
    if not judge_model_id:
        logger.info("debate ai eval skipped: no judge_model_id and no default_model configured")
        return
    logger.info("debate ai eval: using model=%s", judge_model_id)

    analysis_messages = _build_ai_commentary_messages(session)
    analysis_chunks: list[str] = []
    try:
        async for chunk in stream_chat(model=judge_model_id, messages=analysis_messages):
            if await request.is_disconnected():
                return
            delta = strip_loose_think_tags(str(chunk.get("message", {}).get("content", "") or ""))
            if delta:
                analysis_chunks.append(delta)
                yield json.dumps({"type": "judge_analysis_token", "content": delta}, ensure_ascii=False) + "\n"
    except Exception as exc:
        logger.warning("debate ai commentary stream error: %s", exc, exc_info=True)

    analysis_markdown = "".join(analysis_chunks).strip()
    eval_messages = _build_ai_evaluation_messages(session, commentary_markdown=analysis_markdown)
    ai_eval_chunks: list[str] = []
    try:
        async for chunk in stream_chat(model=judge_model_id, messages=eval_messages):
            if await request.is_disconnected():
                return
            delta = strip_loose_think_tags(str(chunk.get("message", {}).get("content", "") or ""))
            if delta:
                ai_eval_chunks.append(delta)
    except Exception as exc:
        logger.warning("debate ai eval stream error: %s", exc, exc_info=True)
        return

    if not ai_eval_chunks:
        logger.warning("debate ai eval: model returned empty response")
        return

    raw = "".join(ai_eval_chunks).strip()
    suggestion = _parse_ai_evaluation(raw)
    if not suggestion:
        logger.warning("debate ai eval: failed to parse suggestion from: %.200s", raw)
        return

    if analysis_markdown:
        scoring_json = suggestion.setdefault("scoring_json", {})
        if isinstance(scoring_json, dict):
            scoring_json["analysis_markdown"] = analysis_markdown

    yield json.dumps({"type": "ai_suggestion", "suggestion": suggestion}, ensure_ascii=False) + "\n"


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
        if stage == "free_debate":
            clock_event = _free_debate_clock_event_line(session)
            if clock_event:
                yield clock_event

    if participant is None:
        # 若本次就是进入 judge_decision（含已在 judge_decision 状态），触发 AI 评分
        if session.stage == "judge_decision":
            async for ai_event in _run_ai_evaluation(request=request, session=session):
                if await request.is_disconnected():
                    return
                yield ai_event
        yield json.dumps(
            {
                "type": "done",
                "stage": session.stage,
                "status": session.status,
            },
            ensure_ascii=False,
        ) + "\n"
        return

    current_participant = participant
    while True:
        active_stage = session.stage
        async for event in _stream_speaker_turn(
            db=db,
            session=session,
            participant=current_participant,
            stage=active_stage,
            target_turn_id=_latest_opponent_turn(session, current_participant.side).id if _latest_opponent_turn(session, current_participant.side) else None,
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
            if stage == "free_debate":
                clock_event = _free_debate_clock_event_line(session)
                if clock_event:
                    yield clock_event

        if "judge_decision" in stage_changes:
            db.refresh(session, attribute_names=["turns", "participants"])
            async for ai_event in _run_ai_evaluation(request=request, session=session):
                if await request.is_disconnected():
                    return
                yield ai_event
            break

        if active_stage != "free_debate" or session.stage != "free_debate":
            break

        current_participant = _participant_by_side(session, _next_free_debate_side(session))

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

    if session.stage == "free_debate":
        state = _ensure_free_debate_state(session)
        if state is not None and _is_free_debate_over(session, state):
            session.stage = _next_stage(session, "free_debate")
            session.status = "running" if session.stage != "judge_decision" else "waiting_judge"
            session.updated_at = datetime.utcnow()
            db.add(session)
            db.commit()
            db.refresh(session)
            yield json.dumps(
                {
                    "type": "stage_changed",
                    "stage": session.stage,
                    "status": session.status,
                },
                ensure_ascii=False,
            ) + "\n"
            if session.stage == "judge_decision":
                async for ai_event in _run_ai_evaluation(request=request, session=session):
                    if await request.is_disconnected():
                        return
                    yield ai_event
            yield json.dumps(
                {
                    "type": "done",
                    "stage": session.stage,
                    "status": session.status,
                },
                ensure_ascii=False,
            ) + "\n"
            return

    for side in target_sides:
        if session.stage == "free_debate":
            state = _free_debate_state(session)
            if state is not None and (
                (side == "pro" and state["pro_remaining_ms"] <= 0)
                or (side == "con" and state["con_remaining_ms"] <= 0)
            ):
                continue
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
        if session.stage == "free_debate":
            stage_changes = _advance_after_generated_turn(session, "free_debate")
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
            if "judge_decision" in stage_changes:
                db.refresh(session, attribute_names=["turns", "participants"])
                async for ai_event in _run_ai_evaluation(request=request, session=session):
                    if await request.is_disconnected():
                        return
                    yield ai_event
            if session.stage != "free_debate":
                break

    if session.stage == question_turn.stage:
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



async def debate_decision_event_stream(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    payload: DebateJudgeDecisionIn,
):
    # 1. 保存裁决
    if session.judge_decision is None:
        decision = DebateJudgeDecision(session=session)
    else:
        decision = session.judge_decision

    decision.winner_side, resolved_scoring = _normalize_decision_scoring(
        winner_side=payload.winner_side,
        scoring_json=payload.scoring_json or {},
    )
    decision.judge_comment = payload.judge_comment.strip()
    decision.scoring_json = json.dumps(resolved_scoring, ensure_ascii=False)
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

    # 2. 发送 decision_saved 事件（立即响应裁决结果）
    yield json.dumps(
        {
            "type": "decision_saved",
            "judge_decision": _decision_payload(session.judge_decision).model_dump(mode="json"),
            "status": session.status,
            "stage": session.stage,
        },
        ensure_ascii=False,
    ) + "\n"

    # 3. 流式生成 summary（使用 AI 裁判模型，若未配置则降级到默认模型）
    # 提前缓存关键字段，防止 async 边界后 SQLAlchemy 对象 detach 导致访问失败
    session_config = _config(session)
    judge_model_id = str(session_config.get("judge_model_id", "")).strip()
    _decision_obj = session.judge_decision
    _winner_side = _decision_obj.winner_side if _decision_obj else "draw"
    _judge_note = _decision_obj.judge_comment if _decision_obj else ""
    _transcript_for_fallback = _recent_transcript(session, limit=999)

    summary_model = judge_model_id or settings.default_model
    messages = _build_summary_messages(session)
    summary_chunks: list[str] = []
    try:
        async for chunk in stream_chat(model=summary_model, messages=messages):
            if await request.is_disconnected():
                break
            delta = strip_loose_think_tags(str(chunk.get("message", {}).get("content", "") or ""))
            if delta:
                summary_chunks.append(delta)
                yield json.dumps(
                    {"type": "summary_token", "content": delta},
                    ensure_ascii=False,
                ) + "\n"
    except Exception:
        winner_label = {"pro": "正方", "con": "反方"}.get(_winner_side, "正方")
        fallback = (
            "为什么我方赢\n"
            f"1. 裁判最终判定{winner_label}占优。\n"
            f"2. 裁判评语聚焦于：{_judge_note or '本场关键比较已形成胜负结论。'}\n"
            "这场辩论说明了什么\n"
            "这场比赛最后留下的判断是：我方主张在关键比较上更站得住，也更值得被采纳。"
        )
        summary_chunks = [fallback]
        yield json.dumps({"type": "summary_token", "content": fallback}, ensure_ascii=False) + "\n"

    # 4. 保存 summary 并发送 done
    summary = "".join(summary_chunks).strip()
    session.summary_json = json.dumps({"content": summary}, ensure_ascii=False)
    session.updated_at = datetime.utcnow()
    db.add(session)
    db.commit()

    yield json.dumps(
        {"type": "done", "stage": session.stage, "status": session.status},
        ensure_ascii=False,
    ) + "\n"
