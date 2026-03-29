from __future__ import annotations

import json
from threading import Lock

import httpx
from sqlalchemy.orm import Session

from ..chat.types import ChatMessagePayload
from ..llm import model_provider_and_name, stream_chat
from ..retrieval import RetrievalMode, RetrievalPlan
from ..storage.database import SessionLocal
from ..storage.models import Conversation
from .context import latest_user_query, load_history_messages, save_assistant_message
from .history import MessageHistoryService
from .state import ChatServices


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
    )
    yield json.dumps({"type": "token", "content": refusal_message}, ensure_ascii=False) + "\n"
    yield json.dumps({"type": "done", "assistant_message_id": assistant_message.id}) + "\n"


async def assistant_event_stream(
    *,
    db: Session,
    conversation: Conversation,
    model: str,
    message_history: list[ChatMessagePayload],
    sources: list[dict[str, str | float | None]],
    thinking_enabled: bool | None = None,
):
    assistant_chunks: list[str] = []
    if sources:
        yield json.dumps({"type": "sources", "sources": sources}, ensure_ascii=False) + "\n"

    async for chunk in stream_chat(
        model=model,
        messages=message_history,
        thinking_enabled=thinking_enabled,
    ):
        reasoning_delta = chunk.get("reasoning", {}).get("content", "")
        if reasoning_delta:
            yield json.dumps({"type": "reasoning", "content": reasoning_delta}, ensure_ascii=False) + "\n"

        delta = chunk.get("message", {}).get("content", "")
        if delta:
            assistant_chunks.append(delta)
            yield json.dumps({"type": "token", "content": delta}, ensure_ascii=False) + "\n"

        if chunk.get("done"):
            full_response = "".join(assistant_chunks).strip()
            if full_response:
                assistant_message = save_assistant_message(
                    db=db,
                    conversation=conversation,
                    content=full_response,
                    sources=sources,
                )
                yield json.dumps({"type": "done", "assistant_message_id": assistant_message.id}) + "\n"
                return
            yield json.dumps({"type": "done"}) + "\n"
            return


def retrieval_status_items(*, plan: RetrievalPlan) -> list[str]:
    if plan.mode == "rag":
        return ["Reading notes"]
    if plan.mode == "web":
        return ["Searching"]
    return []


def try_acquire_ollama_chat_lock(*, model: str, lock: Lock) -> bool:
    provider, _ = model_provider_and_name(model)
    if provider != "ollama":
        return False
    return lock.acquire(blocking=False)


async def response_event_stream(
    *,
    services: ChatServices,
    conversation_id: int,
    message_id: int,
    model: str,
    history_message_ids: list[int],
    query: str,
    retrieval_mode: RetrievalMode,
    thinking_enabled: bool | None = None,
):
    provider, _ = model_provider_and_name(model)
    ollama_lock_acquired = try_acquire_ollama_chat_lock(
        model=model,
        lock=services.ollama_chat_lock,
    )
    if provider == "ollama" and not ollama_lock_acquired:
        yield json.dumps(
            {
                "type": "error",
                "message": "Ollama already has another response running. Stop it before starting a new one.",
            },
            ensure_ascii=False,
        ) + "\n"
        return

    yield json.dumps(
        {
            "type": "meta",
            "conversation_id": conversation_id,
            "message_id": message_id,
            "model": model,
        }
    ) + "\n"

    stream_db = SessionLocal()
    try:
        conversation = stream_db.get(Conversation, conversation_id)
        if conversation is None:
            raise RuntimeError("Conversation not found during streaming.")

        history_messages = load_history_messages(stream_db, history_message_ids)
        message_history_service = MessageHistoryService(stream_db, services.attachment_context_service)
        needs_retrieval_grounding = retrieval_mode != "none" and message_history_service.needs_retrieval_grounding(
            messages=history_messages,
        )
        if message_history_service.needs_image_text(model=model, messages=history_messages) or needs_retrieval_grounding:
            yield json.dumps({"type": "status", "items": ["Reading image"]}, ensure_ascii=False) + "\n"

        prepared_history = await message_history_service.prepare(model=model, messages=history_messages)
        prepared_retrieval_history = await message_history_service.prepare_retrieval_history(messages=history_messages)
        if prepared_history.used_image_text or prepared_retrieval_history.used_image_text:
            yield json.dumps({"type": "status", "items": []}, ensure_ascii=False) + "\n"

        retrieval_query = latest_user_query(prepared_retrieval_history.messages, query)
        retrieval_plan = services.retrieval_service.plan_retrieval(
            query=retrieval_query,
            retrieval_mode=retrieval_mode,
        )
        status_items = retrieval_status_items(plan=retrieval_plan)
        if status_items:
            yield json.dumps({"type": "status", "items": status_items}, ensure_ascii=False) + "\n"

        prompt_context = await services.retrieval_service.build_context_payload(
            query=query or retrieval_query,
            plan=retrieval_plan,
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

        hydrated_history = list(prepared_history.messages)
        if prompt_context.context_message:
            hydrated_history = [prompt_context.context_message, *hydrated_history]

        async for part in assistant_event_stream(
            db=stream_db,
            conversation=conversation,
            model=model,
            message_history=hydrated_history,
            sources=prompt_context.sources,
            thinking_enabled=thinking_enabled,
        ):
            yield part
    except httpx.HTTPError as exc:
        stream_db.rollback()
        details = str(exc).strip() or exc.__class__.__name__
        message = (
            "Model service connection failed. Check service URL, API key, and model name. "
            f"Details: {details}"
        )
        yield json.dumps({"type": "error", "message": message}, ensure_ascii=False) + "\n"
    except Exception as exc:  # pragma: no cover
        stream_db.rollback()
        yield json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n"
    finally:
        if ollama_lock_acquired:
            services.ollama_chat_lock.release()
        stream_db.close()
