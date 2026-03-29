from __future__ import annotations

import json

import httpx
from sqlalchemy.orm import Session

from ..chat.types import ChatMessagePayload
from ..llm import stream_chat
from .history import MessageHistoryService
from ..retrieval import PromptContextPayload, RetrievalPlan, strategy_for_tool
from ..storage.database import SessionLocal
from ..storage.models import Conversation
from .context import (
    latest_user_query,
    load_history_messages,
    save_assistant_message,
)
from .state import ChatServices


async def build_prompt_context(
    *,
    services: ChatServices,
    query: str,
    plan: RetrievalPlan,
    use_rag: bool,
    use_web: bool,
) -> PromptContextPayload:
    try:
        return await services.retrieval_service.build_context_payload(
            query=query,
            plan=plan,
            use_rag=use_rag,
            use_web=use_web,
        )
    except RuntimeError as exc:
        raise httpx.HTTPStatusError(
            message=str(exc),
            request=None,
            response=None,
        ) from exc


async def plan_retrieval(
    *,
    services: ChatServices,
    query: str,
    model: str,
    message_history: list[dict[str, str]],
    use_rag: bool,
    use_web: bool,
) -> RetrievalPlan:
    if not query.strip():
        return RetrievalPlan(
            tool="none",
            reason="No text query provided.",
            strategy=strategy_for_tool("none"),
            run_rag=False,
            run_web=False,
            rag_query="",
            web_query="",
        )

    return await services.retrieval_service.plan_retrieval(
        query=query,
        model=model,
        message_history=message_history,
        use_rag=use_rag,
        use_web=use_web,
    )


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
):
    assistant_chunks: list[str] = []
    if sources:
        yield json.dumps({"type": "sources", "sources": sources}, ensure_ascii=False) + "\n"

    async for chunk in stream_chat(model=model, messages=message_history):
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


def tool_plan_event_payload(plan: RetrievalPlan) -> dict[str, object]:
    return {
        "type": "tool_plan",
        "tool": plan.tool,
        "reason": plan.reason,
        "run_rag": plan.run_rag,
        "run_web": plan.run_web,
        "rag_query": plan.rag_query,
        "web_query": plan.web_query,
    }


def retrieval_status_items(*, plan: RetrievalPlan) -> list[str]:
    items: list[str] = []
    if plan.run_rag:
        items.append("Reading notes")
    if plan.run_web:
        items.append("Searching")
    return items


async def response_event_stream(
    *,
    services: ChatServices,
    conversation_id: int,
    message_id: int,
    model: str,
    history_message_ids: list[int],
    query: str,
    use_rag: bool,
    use_web: bool,
):
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
        message_history_service = MessageHistoryService(stream_db, services.image_text_service)
        needs_retrieval_grounding = (use_rag or use_web) and message_history_service.needs_retrieval_grounding(
            messages=history_messages,
        )
        if message_history_service.needs_image_text(model=model, messages=history_messages) or needs_retrieval_grounding:
            yield json.dumps({"type": "status", "items": ["Reading image"]}, ensure_ascii=False) + "\n"

        prepared_history = await message_history_service.prepare(model=model, messages=history_messages)
        prepared_retrieval_history = await message_history_service.prepare_retrieval_history(messages=history_messages)
        if prepared_history.used_image_text or prepared_retrieval_history.used_image_text:
            yield json.dumps({"type": "status", "items": []}, ensure_ascii=False) + "\n"

        planner_query = latest_user_query(prepared_retrieval_history.messages, query)
        retrieval_plan = await plan_retrieval(
            services=services,
            query=planner_query,
            model=model,
            message_history=prepared_retrieval_history.messages,
            use_rag=use_rag,
            use_web=use_web,
        )
        yield json.dumps(tool_plan_event_payload(retrieval_plan), ensure_ascii=False) + "\n"
        status_items = retrieval_status_items(plan=retrieval_plan)
        if status_items:
            yield json.dumps({"type": "status", "items": status_items}, ensure_ascii=False) + "\n"

        prompt_context = await services.retrieval_service.build_context_payload(
            query=query,
            plan=retrieval_plan,
            use_rag=use_rag,
            use_web=use_web,
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
        stream_db.close()
