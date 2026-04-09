from __future__ import annotations

import asyncio
import json
import logging
import re

import httpx
from fastapi import Request
from sqlalchemy.orm import Session

from ..chat.types import ChatMessagePayload
from ..llm import stream_chat
from ..llm.catalog import resolve_context_window, resolve_effective_thinking, resolve_model_route, uses_native_multimodal
from ..llm.thinking import ThinkTagStreamNormalizer, inject_thinking_system_prompt
from ..retrieval import RetrievalMode, RetrievalPlan
from ..storage.database import SessionLocal
from ..storage.models import Conversation
from .context import latest_user_query, load_history_messages, save_assistant_message, select_history_window
from .history import MessageHistoryService
from .prompt_builder import build_prompt_composition
from .strategy import choose_context_strategy
from .state import ChatServices


logger = logging.getLogger("chatchat.chat")
THINK_TAG_ONLY_PATTERN = re.compile(r"</?think>", re.IGNORECASE)


def strip_loose_think_tags(content: str) -> str:
    if not content:
        return content
    return THINK_TAG_ONLY_PATTERN.sub("", content)


def coalesce_leading_system_messages(messages: list[ChatMessagePayload]) -> list[ChatMessagePayload]:
    system_contents: list[str] = []
    consumed = 0
    for message in messages:
        if message.role != "system":
            break
        if message.images or message.documents or message.files:
            break
        system_contents.append(message.content.strip())
        consumed += 1

    if consumed <= 1:
        return messages

    merged_system = "\n\n".join(content for content in system_contents if content)
    return [ChatMessagePayload(role="system", content=merged_system), *messages[consumed:]]


async def refusal_stream(
    *,
    db: Session,
    conversation: Conversation,
    refusal_message: str,
):
    assistant_message = save_assistant_message(
        db=db,
        conversation=conversation,
        content=refusal_message,
        sources=[],
        context_payload=None,
    )
    yield json.dumps({"type": "token", "content": refusal_message}, ensure_ascii=False) + "\n"
    yield json.dumps(
        {
            "type": "done",
            "assistant_message_id": assistant_message.id,
            "conversation_title": conversation.title,
            "content": refusal_message,
        },
        ensure_ascii=False,
    ) + "\n"


async def assistant_event_stream(
    *,
    services: ChatServices,
    db: Session,
    conversation: Conversation,
    model: str,
    user_message_id: int,
    message_history: list[ChatMessagePayload],
    sources: list[dict[str, str | float | None]],
    context_payload: dict[str, object] | None = None,
    thinking_enabled: bool | None = None,
):
    assistant_chunks: list[str] = []
    reasoning_chunks: list[str] = []
    route = resolve_model_route(model)
    effective_thinking = resolve_effective_thinking(
        model,
        thinking_enabled,
        thinking_mode=route["thinking_mode"] if route else None,
    )
    show_reasoning = effective_thinking is not False
    thinking_normalizer = ThinkTagStreamNormalizer(emit_reasoning=show_reasoning)
    if sources:
        yield json.dumps({"type": "sources", "sources": sources}, ensure_ascii=False) + "\n"

    normalized_history = coalesce_leading_system_messages(message_history)
    prepared_message_history = inject_thinking_system_prompt(
        model=model,
        messages=normalized_history,
        thinking_enabled=effective_thinking,
    )

    async for chunk in stream_chat(
        model=model,
        messages=prepared_message_history,
        thinking_enabled=effective_thinking,
    ):
        reasoning_delta = chunk.get("reasoning", {}).get("content", "") if show_reasoning else ""
        delta = chunk.get("message", {}).get("content", "")
        normalized_reasoning, normalized_answer = thinking_normalizer.feed(delta)

        if normalized_reasoning:
            reasoning_delta = f"{reasoning_delta}{normalized_reasoning}"
        if reasoning_delta:
            reasoning_chunks.append(reasoning_delta)
            yield json.dumps({"type": "reasoning", "content": reasoning_delta}, ensure_ascii=False) + "\n"

        if normalized_answer:
            clean_answer = strip_loose_think_tags(normalized_answer)
            if not clean_answer:
                continue
            assistant_chunks.append(clean_answer)
            try:
                yield json.dumps({"type": "token", "content": clean_answer}, ensure_ascii=False) + "\n"
            except Exception as exc:
                logger.exception("failed to yield token | error=%s", exc)
                raise

        if chunk.get("done"):
            tail_reasoning, tail_answer = thinking_normalizer.flush()
            if show_reasoning and tail_reasoning:
                reasoning_chunks.append(tail_reasoning)
                yield json.dumps({"type": "reasoning", "content": tail_reasoning}, ensure_ascii=False) + "\n"
            if tail_answer:
                clean_tail_answer = strip_loose_think_tags(tail_answer)
                if clean_tail_answer:
                    assistant_chunks.append(clean_tail_answer)
                    yield json.dumps({"type": "token", "content": clean_tail_answer}, ensure_ascii=False) + "\n"

            full_response = "".join(assistant_chunks).strip()
            full_reasoning = "".join(reasoning_chunks).strip()
            if full_response:
                assistant_message = save_assistant_message(
                    db=db,
                    conversation=conversation,
                    content=full_response,
                    reasoning=full_reasoning or None,
                    sources=sources,
                    context_payload=context_payload,
                )
                services.memory_service.schedule_refresh(
                    conversation_id=conversation.id,
                    user_message_id=user_message_id,
                    assistant_message_id=assistant_message.id,
                    response_model=model,
                )
                yield json.dumps(
                    {
                        "type": "done",
                        "assistant_message_id": assistant_message.id,
                        "conversation_title": conversation.title,
                        "content": full_response,
                    },
                    ensure_ascii=False,
                ) + "\n"
                return
            yield json.dumps({"type": "done"}) + "\n"
            return


def retrieval_status_items(*, plan: RetrievalPlan, include_file_context: bool) -> list[str]:
    if include_file_context:
        return ["Reading files"]
    if plan.mode == "rag":
        return ["Reading notes"]
    if plan.mode == "web":
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


async def response_event_stream(
    *,
    services: ChatServices,
    request: Request,
    conversation_id: int,
    message_id: int,
    model: str,
    history_message_ids: list[int],
    query: str,
    retrieval_mode: RetrievalMode,
    thinking_enabled: bool | None = None,
):
    yield json.dumps(
        {
            "type": "meta",
            "conversation_id": conversation_id,
            "message_id": message_id,
            "model": model,
        }
    ) + "\n"

    reservation = None
    stream_db = SessionLocal()
    try:
        conversation = stream_db.get(Conversation, conversation_id)
        if conversation is None:
            raise RuntimeError("Conversation not found during streaming.")

        all_history_messages = load_history_messages(stream_db, history_message_ids)
        model_context_window = resolve_context_window(model)
        history_budget = services.history_token_budget
        summary_budget = services.summary_token_budget
        if isinstance(model_context_window, int) and model_context_window > 0:
            # Reserve token headroom for generation, tools, and retrieval snippets.
            history_budget = min(history_budget, max(900, int(model_context_window * 0.36)))
            summary_budget = min(summary_budget, max(450, int(model_context_window * 0.14)))

        native_multimodal = uses_native_multimodal(model)
        strategy = choose_context_strategy(
            query=query,
            retrieval_mode=retrieval_mode,
            has_conversation_attachments=any(message.attachments for message in all_history_messages),
            default_history_budget=history_budget,
            default_summary_budget=summary_budget,
        )
        history_window = select_history_window(
            all_history_messages,
            message_limit=services.history_message_limit,
            token_budget=strategy.history_token_budget,
        )
        include_image_context = not native_multimodal
        include_file_context = strategy.file_retrieval_enabled and not native_multimodal
        message_history_service = MessageHistoryService(stream_db, services.attachment_context_service)
        needs_retrieval_grounding = include_file_context and retrieval_mode != "none" and message_history_service.needs_retrieval_grounding(
            messages=history_window.recent_messages,
        )
        if message_history_service.needs_image_text(model=model, messages=history_window.recent_messages) or needs_retrieval_grounding:
            yield json.dumps({"type": "status", "items": ["Reading attachments"]}, ensure_ascii=False) + "\n"

        prepared_history = await message_history_service.prepare(model=model, messages=history_window.recent_messages)
        prepared_retrieval_history = await message_history_service.prepare_retrieval_history(
            model=model,
            messages=history_window.recent_messages,
        )
        if prepared_history.used_image_text or prepared_retrieval_history.used_image_text:
            yield json.dumps({"type": "status", "items": []}, ensure_ascii=False) + "\n"

        retrieval_query = latest_user_query(prepared_retrieval_history.messages, query)
        memory_prompt = services.memory_service.build_prompt_payload(
            db=stream_db,
            user_id=conversation.user_id or 0,
            conversation_id=conversation.id,
            query=query or retrieval_query,
        )
        retrieval_plan = services.retrieval_service.plan_retrieval(
            query=retrieval_query,
            retrieval_mode=retrieval_mode,
        )
        status_items = retrieval_status_items(plan=retrieval_plan, include_file_context=include_file_context)
        if status_items:
            yield json.dumps({"type": "status", "items": status_items}, ensure_ascii=False) + "\n"

        prompt_context = await services.retrieval_service.build_context_payload(
            db=stream_db,
            user_id=conversation.user_id or 0,
            query=query or retrieval_query,
            plan=retrieval_plan,
            retrieval_messages=prepared_retrieval_history.messages,
            conversation_messages=all_history_messages,
            include_file_context=include_file_context,
            include_image_context=include_image_context,
        )

        if status_items:
            yield json.dumps({"type": "status", "items": []}, ensure_ascii=False) + "\n"

        if prompt_context.should_refuse and prompt_context.refusal_message:
            async for part in refusal_stream(
                db=stream_db,
                conversation=conversation,
                refusal_message=prompt_context.refusal_message,
            ):
                yield part
            return

        prompt_composition = build_prompt_composition(
            query=query or retrieval_query,
            history_window=history_window,
            strategy=strategy,
            memory_prompt=memory_prompt,
            retrieval_plan=retrieval_plan,
            retrieval_payload=prompt_context,
        )
        hydrated_history = [*prompt_composition.prefix_messages, *prepared_history.messages]
        if prompt_composition.inspection.get("sections"):
            yield json.dumps(
                {"type": "context", "context": prompt_composition.inspection},
                ensure_ascii=False,
            ) + "\n"

        reservation = await services.model_execution_coordinator.reserve(model)
        if reservation.queued:
            yield json.dumps({"type": "status", "items": ["Waiting for model"]}, ensure_ascii=False) + "\n"

        await wait_for_model_turn(
            request=request,
            reservation=reservation,
        )

        if reservation.queued:
            yield json.dumps({"type": "status", "items": []}, ensure_ascii=False) + "\n"

        async for part in assistant_event_stream(
            services=services,
            db=stream_db,
            conversation=conversation,
            model=model,
            user_message_id=message_id,
            message_history=hydrated_history,
            sources=prompt_context.sources,
            context_payload=prompt_composition.inspection,
            thinking_enabled=thinking_enabled,
        ):
            yield part
    except httpx.HTTPError as exc:
        stream_db.rollback()
        logger.exception(
            "chat stream http error | conversation_id=%s | message_id=%s | model=%s",
            conversation_id,
            message_id,
            model,
        )
        details = str(exc).strip() or exc.__class__.__name__
        message = (
            "Model service connection failed. Check service URL, API key, and model name. "
            f"Details: {details}"
        )
        yield json.dumps({"type": "error", "message": message}, ensure_ascii=False) + "\n"
    except Exception as exc:  # pragma: no cover
        stream_db.rollback()
        logger.exception(
            "chat stream unexpected error | conversation_id=%s | message_id=%s | model=%s",
            conversation_id,
            message_id,
            model,
        )
        yield json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n"
    finally:
        if reservation is not None:
            await reservation.release()
        stream_db.close()
