from __future__ import annotations

import json
from datetime import datetime

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from .config import settings
from .database import Base, engine, ensure_schema, get_db
from .models import Conversation, Message
from .providers import (
    build_model_options,
    list_ollama_models,
    list_openai_models,
    normalize_model,
    stream_chat,
)
from .rag import RagService
from .retrieval import PromptContextPayload, RetrievalPlan, RetrievalService, ToolPlannerService
from .schemas import (
    ChatRequest,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdate,
    RagReindexResult,
    RagStatus,
    RegenerateRequest,
)
from .websearch import WebSearchService

app = FastAPI(title=settings.app_name)
rag_service = RagService(settings)
web_search_service = WebSearchService(settings)
tool_planner_service = ToolPlannerService()
retrieval_service = RetrievalService(settings, rag_service, web_search_service, tool_planner_service)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def save_assistant_message(
    *,
    db: Session,
    conversation: Conversation,
    content: str,
    sources: list[dict[str, str | float | None]],
) -> Message:
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        sources_json=json.dumps(sources, ensure_ascii=False),
    )
    conversation.updated_at = datetime.utcnow()
    db.add(assistant_message)
    db.add(conversation)
    db.commit()
    db.refresh(assistant_message)
    return assistant_message


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema()


@app.get("/api/health")
async def healthcheck():
    return {"status": "ok"}


@app.get("/api/models")
async def list_models():
    ollama_models = await list_ollama_models()
    openai_models = await list_openai_models()
    models = [*ollama_models, *openai_models]

    default_model = normalize_model(settings.default_model)

    return {"models": build_model_options(models), "default_model": default_model}


@app.get("/api/rag/status", response_model=RagStatus)
async def get_rag_status():
    return RagStatus(**rag_service.status())


@app.post("/api/rag/reindex", response_model=RagReindexResult)
async def reindex_rag():
    return RagReindexResult(**(await rag_service.reindex()))


@app.get("/api/conversations", response_model=list[ConversationSummary])
def list_conversations(db: Session = Depends(get_db)):
    conversations = db.scalars(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .order_by(desc(Conversation.updated_at), desc(Conversation.id))
    ).all()

    items: list[ConversationSummary] = []
    for conversation in conversations:
        last_message = conversation.messages[-1].content if conversation.messages else ""
        items.append(
            ConversationSummary(
                id=conversation.id,
                title=conversation.title,
                model=conversation.model,
                updated_at=conversation.updated_at,
                last_message_preview=last_message[:80],
            )
        )
    return items


@app.post("/api/conversations", response_model=ConversationSummary)
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db)):
    conversation = Conversation(
        title=payload.title,
        model=payload.model or normalize_model(settings.default_model),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        model=conversation.model,
        updated_at=conversation.updated_at,
        last_message_preview="",
    )


@app.get("/api/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.get(
        Conversation,
        conversation_id,
        options=[selectinload(Conversation.messages)],
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.patch("/api/conversations/{conversation_id}", response_model=ConversationSummary)
def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
):
    conversation = db.get(
        Conversation,
        conversation_id,
        options=[selectinload(Conversation.messages)],
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.title = payload.title.strip()
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    last_message = conversation.messages[-1].content if conversation.messages else ""
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        model=conversation.model,
        updated_at=conversation.updated_at,
        last_message_preview=last_message[:80],
    )


@app.delete("/api/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conversation)
    db.commit()


@app.post("/api/chat/regenerate")
async def regenerate_chat(payload: RegenerateRequest, db: Session = Depends(get_db)):
    conversation = db.get(
        Conversation,
        payload.conversation_id,
        options=[selectinload(Conversation.messages)],
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if payload.model and conversation.model != payload.model:
        conversation.model = payload.model
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    target_index = next(
        (
            index
            for index, message in enumerate(conversation.messages)
            if message.id == payload.assistant_message_id and message.role == "assistant"
        ),
        None,
    )
    if target_index is None:
        raise HTTPException(status_code=404, detail="Assistant message not found")

    source_user = next(
        (
            message
            for message in reversed(conversation.messages[:target_index])
            if message.role == "user"
        ),
        None,
    )
    if source_user is None:
        raise HTTPException(status_code=400, detail="Source user message not found")

    message_history = [
        {"role": message.role, "content": message.content}
        for message in conversation.messages[:target_index]
    ]
    regenerated_user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=source_user.content,
    )
    conversation.updated_at = datetime.utcnow()
    db.add(regenerated_user_message)
    db.add(conversation)
    db.commit()
    db.refresh(regenerated_user_message)

    return StreamingResponse(
        _response_event_stream(
            db=db,
            conversation=conversation,
            message_id=regenerated_user_message.id,
            model=conversation.model,
            message_history=message_history,
            query=source_user.content,
            use_rag=payload.use_rag,
            use_web=payload.use_web,
        ),
        media_type="application/x-ndjson",
    )


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatRequest, db: Session = Depends(get_db)):
    content = payload.message.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    conversation: Conversation | None = None
    if payload.conversation_id is not None:
        conversation = db.get(
            Conversation,
            payload.conversation_id,
            options=[selectinload(Conversation.messages)],
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

    if conversation is None:
        conversation = Conversation(
            title=content[:48] or "New chat",
            model=payload.model or normalize_model(settings.default_model),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    if payload.model and conversation.model != payload.model:
        conversation.model = payload.model
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=content,
    )
    conversation.updated_at = datetime.utcnow()
    db.add(user_message)
    db.add(conversation)
    db.commit()
    db.refresh(user_message)

    conversation = db.get(
        Conversation,
        conversation.id,
        options=[selectinload(Conversation.messages)],
    )
    assert conversation is not None

    message_history = [
        {"role": message.role, "content": message.content}
        for message in conversation.messages
    ]
    return StreamingResponse(
        _response_event_stream(
            db=db,
            conversation=conversation,
            message_id=user_message.id,
            model=conversation.model,
            message_history=message_history,
            query=content,
            use_rag=payload.use_rag,
            use_web=payload.use_web,
        ),
        media_type="application/x-ndjson",
    )


async def _build_prompt_context(
    *,
    query: str,
    plan: RetrievalPlan,
    use_rag: bool,
    use_web: bool,
) -> PromptContextPayload:
    try:
        return await retrieval_service.build_context_payload(
            query=query,
            plan=plan,
            use_rag=use_rag,
            use_web=use_web,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Retrieval service request failed: {exc}",
        ) from exc


async def _plan_retrieval(
    *,
    query: str,
    model: str,
    message_history: list[dict[str, str]],
    use_rag: bool,
    use_web: bool,
) -> RetrievalPlan:
    try:
        return await retrieval_service.plan_retrieval(
            query=query,
            model=model,
            message_history=message_history,
            use_rag=use_rag,
            use_web=use_web,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Tool planner request failed: {exc}",
        ) from exc


async def _refusal_stream(
    *,
    db: Session,
    conversation: Conversation,
    message_id: int,
    model: str,
    refusal_message: str,
):
    assistant_message = save_assistant_message(
        db=db,
        conversation=conversation,
        content=refusal_message,
        sources=[],
    )
    yield json.dumps({"type": "token", "content": refusal_message}) + "\n"
    yield json.dumps({"type": "done", "assistant_message_id": assistant_message.id}) + "\n"


async def _response_event_stream(
    *,
    db: Session,
    conversation: Conversation,
    message_id: int,
    model: str,
    message_history: list[dict[str, str]],
    query: str,
    use_rag: bool,
    use_web: bool,
):
    yield json.dumps(
        {
            "type": "meta",
            "conversation_id": conversation.id,
            "message_id": message_id,
            "model": model,
        }
    ) + "\n"

    try:
        retrieval_plan = await _plan_retrieval(
            query=query,
            model=model,
            message_history=message_history,
            use_rag=use_rag,
            use_web=use_web,
        )
        yield json.dumps(_tool_plan_event_payload(retrieval_plan), ensure_ascii=False) + "\n"
        status_items = _retrieval_status_items(plan=retrieval_plan)
        if status_items:
            yield json.dumps({"type": "status", "items": status_items}, ensure_ascii=False) + "\n"

        prompt_context = await _build_prompt_context(
            query=query,
            plan=retrieval_plan,
            use_rag=use_rag,
            use_web=use_web,
        )

        if status_items:
            yield json.dumps({"type": "status", "items": []}, ensure_ascii=False) + "\n"

        if prompt_context.should_refuse and prompt_context.refusal_message:
            async for part in _refusal_stream(
                db=db,
                conversation=conversation,
                message_id=message_id,
                model=model,
                refusal_message=prompt_context.refusal_message,
            ):
                yield part
            return

        hydrated_history = message_history
        if prompt_context.context_message:
            hydrated_history = [prompt_context.context_message, *message_history]

        async for part in _assistant_event_stream(
            db=db,
            conversation=conversation,
            message_id=message_id,
            model=model,
            message_history=hydrated_history,
            sources=prompt_context.sources,
        ):
            yield part
    except httpx.HTTPError as exc:
        db.rollback()
        message = (
            "Model service connection failed. Check service URL, API key, and model name. "
            f"Details: {exc}"
        )
        yield json.dumps({"type": "error", "message": message}, ensure_ascii=False) + "\n"
    except Exception as exc:  # pragma: no cover
        db.rollback()
        yield json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n"


async def _assistant_event_stream(
    *,
    db: Session,
    conversation: Conversation,
    message_id: int,
    model: str,
    message_history: list[dict[str, str]],
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
                yield json.dumps(
                    {"type": "done", "assistant_message_id": assistant_message.id}
                ) + "\n"
                return
            yield json.dumps({"type": "done"}) + "\n"
            return


def _tool_plan_event_payload(plan: RetrievalPlan) -> dict[str, object]:
    return {
        "type": "tool_plan",
        "tool": plan.tool,
        "reason": plan.reason,
        "run_rag": plan.run_rag,
        "run_web": plan.run_web,
        "rag_query": plan.rag_query,
        "web_query": plan.web_query,
    }


def _retrieval_status_items(*, plan: RetrievalPlan) -> list[str]:
    items: list[str] = []
    if plan.run_rag:
        items.append("Reading notes")
    if plan.run_web:
        items.append("Searching")
    return items
