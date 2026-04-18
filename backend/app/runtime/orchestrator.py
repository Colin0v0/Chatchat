from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

import httpx
from fastapi import Request

from ..chat.context import latest_user_query, load_history_messages, save_assistant_message, select_history_window
from ..chat.history import MessageHistoryService
from ..chat.prompt_builder import build_prompt_composition
from ..chat.strategy import choose_context_strategy
from ..chat.state import ChatServices
from ..providers import resolve_model_profile, resolve_reasoning_profile
from ..runtime.events import (
    CanonicalEvent,
    completed_event,
    context_event,
    failed_event,
    meta_event,
    output_text_delta_event,
    reasoning_delta_event,
    sources_event,
    status_event,
)
from ..runtime.model_runner import stream_model_response
from ..runtime.stream_codec import encode_ndjson_event
from ..storage.database import SessionLocal
from ..storage.models import Conversation, Run, RunEvent

logger = logging.getLogger("chatchat.runtime")


def _append_run_event(buffer: list[RunEvent], run_id: int, event: CanonicalEvent) -> None:
    buffer.append(
        RunEvent(
            run_id=run_id,
            sequence_no=len(buffer) + 1,
            event_type=event.kind,
            payload_json=json.dumps(event.payload, ensure_ascii=False),
        )
    )


def _serialize_event(buffer: list[RunEvent], run_id: int, event: CanonicalEvent) -> str | None:
    _append_run_event(buffer, run_id, event)
    return encode_ndjson_event(event)


def tool_status_items(*, plan, include_file_context: bool) -> list[str]:
    if include_file_context:
        return ["Reading files"]
    if plan.mode == "knowledge":
        return ["Reading notes"]
    if plan.mode == "search":
        return ["Searching"]
    return []


async def wait_for_model_turn(*, request: Request, reservation) -> None:
    try:
        while True:
            try:
                await asyncio.wait_for(reservation.wait(), timeout=0.25)
                break
            except TimeoutError:
                if await request.is_disconnected():
                    raise asyncio.CancelledError
    except BaseException:
        await reservation.release()
        raise


async def stream_chat_run(
    *,
    services: ChatServices,
    request: Request,
    conversation_id: int,
    message_id: int,
    model: str,
    history_message_ids: list[int],
    query: str,
    tool_mode,
    requested_reasoning: bool | None = None,
    requested_reasoning_profile: str | None = None,
):
    profile = resolve_model_profile(model)
    if profile is None:
        line = encode_ndjson_event(failed_event(f"Model not enabled: {model}"))
        if line:
            yield line
        return

    run_db = SessionLocal()
    reservation = None
    buffered_events: list[RunEvent] = []
    try:
        conversation = run_db.get(Conversation, conversation_id)
        if conversation is None:
            raise RuntimeError("Conversation not found during streaming.")

        reasoning_profile = resolve_reasoning_profile(
            model,
            requested_reasoning,
            requested_profile=requested_reasoning_profile,
        )
        run = Run(
            conversation_id=conversation_id,
            user_id=conversation.user_id,
            request_message_id=message_id,
            mode="chat",
            model_id=profile.id,
            provider_family=profile.provider_family,
            reasoning_profile=reasoning_profile,
            status="running",
            metadata_json=json.dumps({"tool_mode": tool_mode}, ensure_ascii=False),
        )
        run_db.add(run)
        run_db.commit()
        run_db.refresh(run)

        meta_line = _serialize_event(
            buffered_events,
            run.id,
            meta_event(
                conversation_id=conversation_id,
                message_id=message_id,
                model=profile.id,
                run_id=run.id,
            ),
        )
        if meta_line:
            yield meta_line

        all_history_messages = load_history_messages(run_db, history_message_ids)
        history_budget = services.history_token_budget
        summary_budget = services.summary_token_budget
        if isinstance(profile.context_window, int) and profile.context_window > 0:
            history_budget = min(history_budget, max(900, int(profile.context_window * 0.36)))
            summary_budget = min(summary_budget, max(450, int(profile.context_window * 0.14)))

        strategy = choose_context_strategy(
            query=query,
            tool_mode=tool_mode,
            has_conversation_attachments=any(message.attachments for message in all_history_messages),
            default_history_budget=history_budget,
            default_summary_budget=summary_budget,
        )
        history_window = select_history_window(
            all_history_messages,
            message_limit=services.history_message_limit,
            token_budget=strategy.history_token_budget,
        )
        include_image_context = profile.native_multimodal_mode == "false"
        include_file_context = strategy.file_retrieval_enabled and profile.native_multimodal_mode != "local"
        message_history_service = MessageHistoryService(run_db, services.attachment_context_service)
        needs_retrieval_grounding = (
            include_file_context
            and tool_mode != "none"
            and message_history_service.needs_retrieval_grounding(model=model, messages=history_window.recent_messages)
        )
        if message_history_service.needs_image_text(model=model, messages=history_window.recent_messages) or needs_retrieval_grounding:
            line = _serialize_event(buffered_events, run.id, status_event(["Reading attachments"]))
            if line:
                yield line

        prepared_history = await message_history_service.prepare(model=model, messages=history_window.recent_messages)
        prepared_retrieval_history = await message_history_service.prepare_retrieval_history(
            model=model,
            messages=history_window.recent_messages,
        )
        if prepared_history.used_image_text or prepared_retrieval_history.used_image_text:
            line = _serialize_event(buffered_events, run.id, status_event([]))
            if line:
                yield line

        retrieval_query = latest_user_query(prepared_retrieval_history.messages, query)
        memory_prompt = services.memory_service.build_prompt_payload(
            db=run_db,
            user_id=conversation.user_id or 0,
            conversation_id=conversation.id,
            query=query or retrieval_query,
        )
        tool_plan = services.tool_runtime.plan_context(
            query=retrieval_query,
            tool_mode=tool_mode,
        )
        status_items = tool_status_items(plan=tool_plan, include_file_context=include_file_context)
        if status_items:
            line = _serialize_event(buffered_events, run.id, status_event(status_items))
            if line:
                yield line

        prompt_context = await services.tool_runtime.build_context_payload(
            db=run_db,
            user_id=conversation.user_id or 0,
            query=query or retrieval_query,
            plan=tool_plan,
            retrieval_messages=prepared_retrieval_history.messages,
            conversation_messages=all_history_messages,
            include_file_context=include_file_context,
            include_image_context=include_image_context,
        )
        if status_items:
            line = _serialize_event(buffered_events, run.id, status_event([]))
            if line:
                yield line

        if prompt_context.sources:
            line = _serialize_event(buffered_events, run.id, sources_event(prompt_context.sources))
            if line:
                yield line

        if prompt_context.should_refuse and prompt_context.refusal_message:
            assistant_message = save_assistant_message(
                db=run_db,
                conversation=conversation,
                content=prompt_context.refusal_message,
                sources=[],
                context_payload=None,
            )
            run.response_message_id = assistant_message.id
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            run_db.add(run)
            _append_run_event(buffered_events, run.id, output_text_delta_event(prompt_context.refusal_message))
            _append_run_event(
                buffered_events,
                run.id,
                completed_event(
                    assistant_message_id=assistant_message.id,
                    conversation_title=conversation.title,
                    content=prompt_context.refusal_message,
                    run_id=run.id,
                ),
            )
            run_db.add_all(buffered_events)
            run_db.commit()

            for event in (
                output_text_delta_event(prompt_context.refusal_message),
                completed_event(
                    assistant_message_id=assistant_message.id,
                    conversation_title=conversation.title,
                    content=prompt_context.refusal_message,
                    run_id=run.id,
                ),
            ):
                line = encode_ndjson_event(event)
                if line:
                    yield line
            return

        prompt_composition = build_prompt_composition(
            query=query or retrieval_query,
            history_window=history_window,
            strategy=strategy,
            memory_prompt=memory_prompt,
            tool_plan=tool_plan,
            retrieval_payload=prompt_context,
        )
        hydrated_history = [*prompt_composition.prefix_messages, *prepared_history.messages]
        if prompt_composition.inspection.get("sections"):
            line = _serialize_event(buffered_events, run.id, context_event(prompt_composition.inspection))
            if line:
                yield line

        reservation = await services.model_execution_coordinator.reserve(model)
        if reservation.queued:
            line = _serialize_event(buffered_events, run.id, status_event(["Waiting for model"]))
            if line:
                yield line

        await wait_for_model_turn(request=request, reservation=reservation)
        if reservation.queued:
            line = _serialize_event(buffered_events, run.id, status_event([]))
            if line:
                yield line

        answer_chunks: list[str] = []
        reasoning_chunks: list[str] = []
        async for chunk in stream_model_response(
            model=model,
            messages=hydrated_history,
            requested_reasoning=requested_reasoning,
            requested_reasoning_profile=requested_reasoning_profile,
        ):
            if chunk.reasoning_delta:
                reasoning_chunks.append(chunk.reasoning_delta)
                line = _serialize_event(buffered_events, run.id, reasoning_delta_event(chunk.reasoning_delta))
                if line:
                    yield line
                continue

            if chunk.output_text_delta:
                answer_chunks.append(chunk.output_text_delta)
                line = _serialize_event(buffered_events, run.id, output_text_delta_event(chunk.output_text_delta))
                if line:
                    yield line
                continue

            if chunk.done:
                break

        full_response = "".join(answer_chunks).strip()
        full_reasoning = "".join(reasoning_chunks).strip()
        assistant_message = save_assistant_message(
            db=run_db,
            conversation=conversation,
            content=full_response,
            reasoning=full_reasoning or None,
            sources=prompt_context.sources,
            context_payload=prompt_composition.inspection,
        )
        services.memory_service.schedule_refresh(
            conversation_id=conversation.id,
            user_message_id=message_id,
            assistant_message_id=assistant_message.id,
            response_model=model,
        )

        run.response_message_id = assistant_message.id
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        run_db.add(run)
        _append_run_event(
            buffered_events,
            run.id,
            completed_event(
                assistant_message_id=assistant_message.id,
                conversation_title=conversation.title,
                content=full_response,
                run_id=run.id,
            ),
        )
        run_db.add_all(buffered_events)
        run_db.commit()

        done_line = encode_ndjson_event(
            completed_event(
                assistant_message_id=assistant_message.id,
                conversation_title=conversation.title,
                content=full_response,
                run_id=run.id,
            )
        )
        if done_line:
            yield done_line
    except httpx.HTTPError as exc:
        run_db.rollback()
        details = str(exc).strip() or exc.__class__.__name__
        message = (
            "Model service connection failed. Check service URL, API key, and model name. "
            f"Details: {details}"
        )
        if "run" in locals():
            run.status = "failed"
            run.error_code = exc.__class__.__name__
            run.error_message = message
            run.completed_at = datetime.utcnow()
            run_db.add(run)
            _append_run_event(buffered_events, run.id, failed_event(message))
            run_db.add_all(buffered_events)
            run_db.commit()
        line = encode_ndjson_event(failed_event(message))
        if line:
            yield line
    except Exception as exc:  # pragma: no cover
        run_db.rollback()
        logger.exception(
            "runtime chat stream error | conversation_id=%s | message_id=%s | model=%s",
            conversation_id,
            message_id,
            model,
        )
        if "run" in locals():
            run.status = "failed"
            run.error_code = exc.__class__.__name__
            run.error_message = str(exc)
            run.completed_at = datetime.utcnow()
            run_db.add(run)
            _append_run_event(buffered_events, run.id, failed_event(str(exc)))
            run_db.add_all(buffered_events)
            run_db.commit()
        line = encode_ndjson_event(failed_event(str(exc)))
        if line:
            yield line
    finally:
        if reservation is not None:
            await reservation.release()
        run_db.close()
