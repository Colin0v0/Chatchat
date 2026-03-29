from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from .chat_types import ChatMessagePayload
from .config import settings
from .database import Base, SessionLocal, engine, ensure_schema, get_db
from .media import MEDIA_ROOT, persist_uploaded_images, remove_media_files
from .image_text import ImageTextService
from .message_history import MessageHistoryService
from .models import Conversation, Message, MessageAttachment
from .providers import (
    build_model_options,
    list_ollama_models,
    list_openai_models,
    normalize_model,
    stream_chat,
)
from .rag import RagService
from .retrieval import (
    PromptContextPayload,
    RetrievalPlan,
    RetrievalService,
    ToolPlannerService,
    strategy_for_tool,
)
from .schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdate,
    RagReindexResult,
    RagStatus,
    RegenerateRequest,
)
from .websearch import WebSearchService

MESSAGE_LOAD_OPTION = selectinload(Conversation.messages).selectinload(Message.attachments)

app = FastAPI(title=settings.app_name)
app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")
rag_service = RagService(settings)
web_search_service = WebSearchService(settings)
image_text_service = ImageTextService(
    min_confidence=settings.image_ocr_min_confidence,
    text_max_chars=settings.image_text_max_chars,
    vision_model_name=settings.image_vision_model,
    vision_prompt=settings.image_vision_prompt,
    vision_max_new_tokens=settings.image_vision_max_new_tokens,
    vision_num_beams=settings.image_vision_num_beams,
    vision_summary_max_chars=settings.image_vision_summary_max_chars,
    vision_device=settings.image_vision_device,
)
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


def _conversation_options() -> list:
    return [MESSAGE_LOAD_OPTION]


def _message_preview(message: Optional[Message]) -> str:
    if message is None:
        return ""
    content = message.content.strip()
    if content:
        return content[:80]
    if message.attachments:
        return "[Image]"
    return ""


def _conversation_title(content: str, uploaded_count: int) -> str:
    normalized = content.strip()
    if normalized:
        return normalized[:48]
    if uploaded_count:
        return "Image chat"
    return "New chat"


def _conversation_media_paths(conversation: Conversation) -> list[str]:
    return [attachment.relative_path for message in conversation.messages for attachment in message.attachments]


def _history_message_ids(messages: list[Message]) -> list[int]:
    return [message.id for message in messages]


def _latest_user_query(message_history: list[dict[str, str]], fallback: str) -> str:
    for message in reversed(message_history):
        if message.get("role") == "user":
            content = message.get("content", "").strip()
            if content:
                return content
    return fallback.strip()


def _load_history_messages(db: Session, message_ids: list[int]) -> list[Message]:
    if not message_ids:
        return []

    loaded_messages = db.scalars(
        select(Message)
        .options(selectinload(Message.attachments))
        .where(Message.id.in_(message_ids))
    ).all()
    messages_by_id = {message.id: message for message in loaded_messages}
    return [messages_by_id[message_id] for message_id in message_ids if message_id in messages_by_id]


def _append_message_attachments(*, db: Session, message: Message, images) -> None:
    for position, image in enumerate(images):
        db.add(
            MessageAttachment(
                message_id=message.id,
                kind="image",
                original_name=image.original_name,
                mime_type=image.mime_type,
                relative_path=image.relative_path,
                size_bytes=image.size_bytes,
                position=position,
            )
        )


def _clone_message_attachments(*, db: Session, source: Message, target: Message) -> None:
    for position, attachment in enumerate(source.attachments):
        db.add(
            MessageAttachment(
                message_id=target.id,
                kind=attachment.kind,
                original_name=attachment.original_name,
                mime_type=attachment.mime_type,
                relative_path=attachment.relative_path,
                size_bytes=attachment.size_bytes,
                position=position,
            )
        )


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
    default_model = normalize_model(settings.default_model)

    return {
        "models": build_model_options([*ollama_models, *openai_models]),
        "default_model": default_model,
    }


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
        .options(MESSAGE_LOAD_OPTION)
        .order_by(desc(Conversation.updated_at), desc(Conversation.id))
    ).all()

    items: list[ConversationSummary] = []
    for conversation in conversations:
        items.append(
            ConversationSummary(
                id=conversation.id,
                title=conversation.title,
                model=conversation.model,
                updated_at=conversation.updated_at,
                last_message_preview=_message_preview(conversation.messages[-1] if conversation.messages else None),
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
        options=_conversation_options(),
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
        options=_conversation_options(),
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.title = payload.title.strip()
    conversation.updated_at = datetime.utcnow()
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        model=conversation.model,
        updated_at=conversation.updated_at,
        last_message_preview=_message_preview(conversation.messages[-1] if conversation.messages else None),
    )


@app.delete("/api/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id, options=_conversation_options())
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    remove_media_files(_conversation_media_paths(conversation))
    db.delete(conversation)
    db.commit()


@app.post("/api/chat/regenerate")
async def regenerate_chat(payload: RegenerateRequest, db: Session = Depends(get_db)):
    conversation = db.get(
        Conversation,
        payload.conversation_id,
        options=_conversation_options(),
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

    history_messages = list(conversation.messages[:target_index])
    regenerated_user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=source_user.content,
        image_context=source_user.image_context,
    )
    conversation.updated_at = datetime.utcnow()
    db.add(regenerated_user_message)
    db.flush()
    _clone_message_attachments(db=db, source=source_user, target=regenerated_user_message)
    db.add(conversation)
    db.commit()
    db.refresh(regenerated_user_message)

    return StreamingResponse(
        _response_event_stream(
            conversation_id=conversation.id,
            message_id=regenerated_user_message.id,
            model=conversation.model,
            history_message_ids=_history_message_ids(history_messages),
            query=source_user.content,
            use_rag=payload.use_rag,
            use_web=payload.use_web,
        ),
        media_type="application/x-ndjson",
    )


@app.post("/api/chat/stream")
async def chat_stream(
    conversation_id: Optional[int] = Form(None),
    message: str = Form(""),
    model: Optional[str] = Form(None),
    use_rag: bool = Form(False),
    use_web: bool = Form(False),
    images: Optional[list[UploadFile]] = File(None),
    db: Session = Depends(get_db),
):
    content = message.strip()
    uploads = images or []
    if not content and not uploads:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    conversation: Optional[Conversation] = None
    if conversation_id is not None:
        conversation = db.get(
            Conversation,
            conversation_id,
            options=_conversation_options(),
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

    uploaded_images = []
    try:
        uploaded_images = await persist_uploaded_images(uploads)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not content and not uploaded_images:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        if conversation is None:
            conversation = Conversation(
                title=_conversation_title(content, len(uploaded_images)),
                model=model or normalize_model(settings.default_model),
            )
            db.add(conversation)
            db.flush()

        if model and conversation.model != model:
            conversation.model = model

        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=content,
        )
        conversation.updated_at = datetime.utcnow()
        db.add(user_message)
        db.flush()
        _append_message_attachments(db=db, message=user_message, images=uploaded_images)
        db.add(conversation)
        db.commit()
        db.refresh(user_message)
    except Exception:
        remove_media_files([image.relative_path for image in uploaded_images])
        db.rollback()
        raise

    conversation = db.get(
        Conversation,
        conversation.id,
        options=_conversation_options(),
    )
    assert conversation is not None

    return StreamingResponse(
        _response_event_stream(
            conversation_id=conversation.id,
            message_id=user_message.id,
            model=conversation.model,
            history_message_ids=_history_message_ids(list(conversation.messages)),
            query=content,
            use_rag=use_rag,
            use_web=use_web,
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
    model: str,
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


async def _response_event_stream(
    *,
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

        history_messages = _load_history_messages(stream_db, history_message_ids)
        message_history_service = MessageHistoryService(stream_db, image_text_service)
        needs_retrieval_grounding = (use_rag or use_web) and message_history_service.needs_retrieval_grounding(
            messages=history_messages,
        )
        if message_history_service.needs_image_text(model=model, messages=history_messages) or needs_retrieval_grounding:
            yield json.dumps({"type": "status", "items": ["Reading image"]}, ensure_ascii=False) + "\n"

        prepared_history = await message_history_service.prepare(model=model, messages=history_messages)
        prepared_retrieval_history = await message_history_service.prepare_retrieval_history(messages=history_messages)
        if prepared_history.used_image_text or prepared_retrieval_history.used_image_text:
            yield json.dumps({"type": "status", "items": []}, ensure_ascii=False) + "\n"

        planner_query = _latest_user_query(prepared_retrieval_history.messages, query)
        retrieval_plan = await _plan_retrieval(
            query=planner_query,
            model=model,
            message_history=prepared_retrieval_history.messages,
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
                db=stream_db,
                conversation=conversation,
                model=model,
                refusal_message=prompt_context.refusal_message,
            ):
                yield part
            return

        hydrated_history = list(prepared_history.messages)
        if prompt_context.context_message:
            hydrated_history = [prompt_context.context_message, *hydrated_history]

        async for part in _assistant_event_stream(
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


async def _assistant_event_stream(
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






