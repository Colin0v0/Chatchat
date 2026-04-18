from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import Request
from sqlalchemy.orm import Session

from ...chat.state import get_chat_services
from ...core.config import settings
from ...debate.common import (
    _build_ai_commentary_messages,
    _build_ai_evaluation_messages,
    _build_summary_messages,
    _build_turn_messages,
    _config,
    _ensure_free_debate_state,
    _free_debate_clock_event_line,
    _mark_free_debate_ended,
    _parse_ai_evaluation,
    _save_free_debate_state,
    _set_turn_meta,
    _stage_turn_budget_ms,
    _turn_payload,
    logger,
)
from ...runtime.model_runner import stream_model_response
from ...storage.models import DebateParticipant, DebateSession, DebateTurn


@asynccontextmanager
async def reserve_model_execution(request: Request, model_id: str):
    reservation = None
    try:
        reservation = await get_chat_services(request).model_execution_coordinator.reserve(model_id)
        await reservation.wait()
        yield
    finally:
        if reservation is not None:
            await reservation.release()


async def stream_speaker_turn(
    *,
    db: Session,
    request: Request,
    session: DebateSession,
    participant: DebateParticipant,
    stage: str,
    next_turn_index: int,
    target_turn_id: int | None = None,
    judge_question: str | None = None,
) -> AsyncIterator[str]:
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
        turn_index=next_turn_index,
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
    stream = None

    async def consume_stream() -> AsyncIterator[str]:
        nonlocal truncated

        async for chunk in stream:
            if chunk.done:
                break
            if await request.is_disconnected():
                truncated = bool(answer_chunks or reasoning_chunks)
                break

            elapsed_ms = int((time.monotonic() - turn_started) * 1000)
            if time_budget_ms is not None and elapsed_ms >= time_budget_ms:
                truncated = True
                break

            reasoning_delta = chunk.reasoning_delta
            if reasoning_delta:
                reasoning_chunks.append(reasoning_delta)
                yield json.dumps(
                    {"type": "reasoning", "turn_id": turn.id, "content": reasoning_delta},
                    ensure_ascii=False,
                ) + "\n"

            elapsed_ms = int((time.monotonic() - turn_started) * 1000)
            if time_budget_ms is not None and elapsed_ms >= time_budget_ms:
                truncated = True
                break

            delta = chunk.output_text_delta
            if delta:
                answer_chunks.append(delta)
                yield json.dumps(
                    {"type": "token", "turn_id": turn.id, "content": delta},
                    ensure_ascii=False,
                ) + "\n"

    try:
        async with reserve_model_execution(request, participant.model_id):
            stream = stream_model_response(model=participant.model_id, messages=prompt_messages)
            if time_budget_ms is None:
                async for event in consume_stream():
                    yield event
            else:
                iterator = consume_stream().__aiter__()
                while True:
                    if await request.is_disconnected():
                        truncated = bool(answer_chunks or reasoning_chunks)
                        break
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


async def run_ai_evaluation(*, request: Request, session: DebateSession) -> AsyncIterator[str]:
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
        async with reserve_model_execution(request, judge_model_id):
            async for chunk in stream_model_response(model=judge_model_id, messages=analysis_messages):
                if await request.is_disconnected():
                    return
                delta = chunk.output_text_delta
                if delta:
                    analysis_chunks.append(delta)
                    yield json.dumps({"type": "judge_analysis_token", "content": delta}, ensure_ascii=False) + "\n"
    except Exception as exc:
        logger.warning("debate ai commentary stream error: %s", exc, exc_info=True)

    analysis_markdown = "".join(analysis_chunks).strip()
    eval_messages = _build_ai_evaluation_messages(session, commentary_markdown=analysis_markdown)
    ai_eval_chunks: list[str] = []
    try:
        async with reserve_model_execution(request, judge_model_id):
            async for chunk in stream_model_response(model=judge_model_id, messages=eval_messages):
                if await request.is_disconnected():
                    return
                delta = chunk.output_text_delta
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


async def stream_decision_summary_text(
    *,
    request: Request,
    session: DebateSession,
    judge_note: str,
    winner_side: str,
) -> AsyncIterator[str]:
    session_config = _config(session)
    judge_model_id = str(session_config.get("judge_model_id", "")).strip()
    summary_model = judge_model_id or settings.default_model
    messages = _build_summary_messages(session)

    try:
        async with reserve_model_execution(request, summary_model):
            async for chunk in stream_model_response(model=summary_model, messages=messages):
                if await request.is_disconnected():
                    break
                delta = chunk.output_text_delta
                if delta:
                    yield delta
    except Exception:
        winner_label = {"pro": "正方", "con": "反方"}.get(winner_side, "正方")
        yield (
            "为什么我方赢\n"
            f"1. 裁判最终判定{winner_label}占优。\n"
            f"2. 裁判评语聚焦于：{judge_note or '本场关键比较已形成胜负结论。'}\n"
            "这场辩论说明了什么\n"
            "这场比赛最后留下的判断是：我方主张在关键比较上更站得住，也更值得被采纳。"
        )
