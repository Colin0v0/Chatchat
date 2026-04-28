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
    _build_ai_single_pass_evaluation_messages,
    _build_summary_messages,
    _build_turn_messages,
    _config,
    _ensure_free_debate_state,
    _fallback_ai_evaluation_from_commentary,
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

AI_EVALUATION_STRUCTURED_TIMEOUT_SECONDS = 35
AI_EVALUATION_JSON_MARKER = "<AI_EVAL_JSON>"


def _speaker_clock_event_line(turn_id: int, started_at: str) -> str:
    return json.dumps(
        {"type": "speaker_clock", "turn_id": turn_id, "started_at": started_at},
        ensure_ascii=False,
    ) + "\n"


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
        free_debate_state["active_turn_started_at"] = None
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
    answer_started_at_monotonic: float | None = None
    truncated = False
    stream = None

    def answer_elapsed_ms() -> int:
        if answer_started_at_monotonic is None:
            return 0
        return int((time.monotonic() - answer_started_at_monotonic) * 1000)

    def answer_budget_exhausted() -> bool:
        return (
            time_budget_ms is not None
            and answer_started_at_monotonic is not None
            and answer_elapsed_ms() >= time_budget_ms
        )

    def next_answer_timeout_seconds() -> float | None:
        if time_budget_ms is None or answer_started_at_monotonic is None:
            return None
        remaining_ms = time_budget_ms - answer_elapsed_ms()
        return max(0, remaining_ms) / 1000

    def start_answer_clock() -> list[str]:
        nonlocal answer_started_at_monotonic

        if answer_started_at_monotonic is not None:
            return []

        # 中文注释：辩论计时只统计正式正文输出，不把模型 reasoning / thinking 时间算进发言时间。
        answer_started_at_monotonic = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        _set_turn_meta(turn, answer_started_at=started_at)
        events = [_speaker_clock_event_line(turn.id, started_at)]
        db.add(turn)
        if free_debate_state is not None:
            free_debate_state["active_turn_started_at"] = started_at
            _save_free_debate_state(session, free_debate_state)
            session.updated_at = datetime.utcnow()
            db.add(session)
        db.commit()
        db.refresh(turn)
        if free_debate_state is not None:
            db.refresh(session)
            clock_event = _free_debate_clock_event_line(session)
            if clock_event:
                events.append(clock_event)
        return events

    async def consume_stream() -> AsyncIterator[str]:
        nonlocal truncated

        async for chunk in stream:
            if chunk.done:
                break
            if await request.is_disconnected():
                truncated = bool(answer_chunks or reasoning_chunks)
                break

            if answer_budget_exhausted():
                truncated = True
                break

            reasoning_delta = chunk.reasoning_delta
            if reasoning_delta:
                reasoning_chunks.append(reasoning_delta)
                yield json.dumps(
                    {"type": "reasoning", "turn_id": turn.id, "content": reasoning_delta},
                    ensure_ascii=False,
                ) + "\n"

            if answer_budget_exhausted():
                truncated = True
                break

            delta = chunk.output_text_delta
            if delta:
                for event in start_answer_clock():
                    yield event
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
                    timeout_seconds = next_answer_timeout_seconds()
                    if timeout_seconds == 0:
                        truncated = True
                        break
                    try:
                        event = await asyncio.wait_for(iterator.__anext__(), timeout=timeout_seconds)
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

    elapsed_ms = answer_elapsed_ms()
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

    eval_messages = _build_ai_single_pass_evaluation_messages(session)
    analysis_chunks: list[str] = []
    ai_eval_chunks: list[str] = []
    stream_buffer = ""
    saw_json_marker = False
    model_stream = None
    try:
        async with reserve_model_execution(request, judge_model_id):
            model_stream = stream_model_response(model=judge_model_id, messages=eval_messages)
            iterator = model_stream.__aiter__()
            started_at = time.monotonic()

            while True:
                if await request.is_disconnected():
                    return

                remaining = AI_EVALUATION_STRUCTURED_TIMEOUT_SECONDS - (time.monotonic() - started_at)
                if remaining <= 0:
                    raise asyncio.TimeoutError

                try:
                    chunk = await asyncio.wait_for(iterator.__anext__(), timeout=remaining)
                except StopAsyncIteration:
                    break

                if chunk.done:
                    break

                delta = chunk.output_text_delta
                if not delta:
                    continue

                stream_buffer += delta

                if saw_json_marker:
                    ai_eval_chunks.append(stream_buffer)
                    stream_buffer = ""
                    continue

                marker_index = stream_buffer.find(AI_EVALUATION_JSON_MARKER)
                if marker_index != -1:
                    commentary_delta = stream_buffer[:marker_index].rstrip("\r\n")
                    if commentary_delta:
                        analysis_chunks.append(commentary_delta)
                        yield json.dumps(
                            {"type": "judge_analysis_token", "content": commentary_delta},
                            ensure_ascii=False,
                        ) + "\n"
                    json_remainder = stream_buffer[marker_index + len(AI_EVALUATION_JSON_MARKER):].lstrip("\r\n")
                    if json_remainder:
                        ai_eval_chunks.append(json_remainder)
                    stream_buffer = ""
                    saw_json_marker = True
                    continue

                safe_visible_length = len(stream_buffer) - (len(AI_EVALUATION_JSON_MARKER) - 1)
                if safe_visible_length > 0:
                    commentary_delta = stream_buffer[:safe_visible_length]
                    analysis_chunks.append(commentary_delta)
                    yield json.dumps(
                        {"type": "judge_analysis_token", "content": commentary_delta},
                        ensure_ascii=False,
                    ) + "\n"
                    stream_buffer = stream_buffer[safe_visible_length:]
    except asyncio.TimeoutError:
        logger.warning("debate ai eval: structured scoring timed out after %ss", AI_EVALUATION_STRUCTURED_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("debate ai eval stream error: %s", exc, exc_info=True)
    finally:
        aclose = getattr(model_stream, "aclose", None)
        if callable(aclose):
            try:
                await aclose()
            except Exception:
                logger.debug("debate ai eval stream close failed", exc_info=True)
    if saw_json_marker:
        if stream_buffer:
            ai_eval_chunks.append(stream_buffer)
    elif stream_buffer:
        analysis_chunks.append(stream_buffer)
        yield json.dumps(
            {"type": "judge_analysis_token", "content": stream_buffer},
            ensure_ascii=False,
        ) + "\n"

    analysis_markdown = "".join(analysis_chunks).strip()
    raw = "".join(ai_eval_chunks).strip()
    suggestion = _parse_ai_evaluation(raw) if raw else None
    if raw and not suggestion:
        logger.warning("debate ai eval: failed to parse suggestion from: %.200s", raw)
    if suggestion is None:
        if not raw and analysis_markdown:
            if analysis_markdown.startswith("{"):
                suggestion = _parse_ai_evaluation(analysis_markdown)
                if suggestion is not None:
                    logger.info("debate ai eval: recovered suggestion from JSON-only response without marker")
                    analysis_markdown = ""
            else:
                trailing_json_start = analysis_markdown.rfind("\n{")
                if trailing_json_start != -1:
                    trailing_json = analysis_markdown[trailing_json_start + 1 :].strip()
                    suggestion = _parse_ai_evaluation(trailing_json)
                    if suggestion is not None:
                        logger.info("debate ai eval: recovered suggestion from trailing JSON without marker")
                        analysis_markdown = analysis_markdown[:trailing_json_start].rstrip()
        if not ai_eval_chunks and suggestion is None:
            logger.warning("debate ai eval: model returned empty response")
        if suggestion is None:
            suggestion = _fallback_ai_evaluation_from_commentary(analysis_markdown)
            if suggestion is None:
                return

    if analysis_markdown:
        scoring_json = suggestion.setdefault("scoring_json", {})
        if isinstance(scoring_json, dict) and not str(scoring_json.get("analysis_markdown") or "").strip():
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
