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
from .database import Base, engine, get_db
from .models import Conversation, Message
from .providers import (
    build_model_options,
    list_ollama_models,
    list_openai_models,
    namespaced_model,
    stream_chat,
)
from .schemas import (
    ChatRequest,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
    ConversationUpdate,
    RegenerateRequest,
)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/api/health")
async def healthcheck():
    return {"status": "ok"}


@app.get("/api/models")
async def list_models():
    ollama_models = await list_ollama_models()
    openai_models = await list_openai_models()
    models = [*ollama_models, *openai_models]

    default_model = settings.default_model
    if ":" not in default_model:
        default_model = namespaced_model(settings.default_provider, default_model)

    return {"models": build_model_options(models), "default_model": default_model}


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
        model=payload.model or settings.default_model,
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

    message_history = [
        {"role": message.role, "content": message.content}
        for message in conversation.messages[:target_index]
    ]

    async def event_stream():
        assistant_chunks: list[str] = []
        yield json.dumps(
            {
                "type": "meta",
                "conversation_id": conversation.id,
                "message_id": regenerated_user_message.id,
                "model": conversation.model,
            }
        ) + "\n"

        try:
            async for chunk in stream_chat(model=conversation.model, messages=message_history):
                reasoning_delta = chunk.get("reasoning", {}).get("content", "")
                if reasoning_delta:
                    yield json.dumps({"type": "reasoning", "content": reasoning_delta}) + "\n"

                delta = chunk.get("message", {}).get("content", "")
                if delta:
                    assistant_chunks.append(delta)
                    yield json.dumps({"type": "token", "content": delta}) + "\n"
                if chunk.get("done"):
                    full_response = "".join(assistant_chunks).strip()
                    if full_response:
                        assistant_message = Message(
                            conversation_id=conversation.id,
                            role="assistant",
                            content=full_response,
                        )
                        conversation.updated_at = datetime.utcnow()
                        db.add(assistant_message)
                        db.add(conversation)
                        db.commit()
                        db.refresh(assistant_message)
                        yield json.dumps(
                            {"type": "done", "assistant_message_id": assistant_message.id}
                        ) + "\n"
                        return
                    yield json.dumps({"type": "done"}) + "\n"
                    return
        except httpx.HTTPError as exc:
            db.rollback()
            message = f"Model service connection failed. Check service URL, API key, and model name. Details: {exc}"
            yield json.dumps({"type": "error", "message": message}) + "\n"
            return
        except Exception as exc:  # pragma: no cover
            db.rollback()
            yield json.dumps({"type": "error", "message": str(exc)}) + "\n"
            return

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


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
            model=payload.model or settings.default_model,
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

    async def event_stream():
        assistant_chunks: list[str] = []
        yield json.dumps(
            {
                "type": "meta",
                "conversation_id": conversation.id,
                "message_id": user_message.id,
                "model": conversation.model,
            }
        ) + "\n"

        try:
            async for chunk in stream_chat(model=conversation.model, messages=message_history):
                reasoning_delta = chunk.get("reasoning", {}).get("content", "")
                if reasoning_delta:
                    yield json.dumps({"type": "reasoning", "content": reasoning_delta}) + "\n"

                delta = chunk.get("message", {}).get("content", "")
                if delta:
                    assistant_chunks.append(delta)
                    yield json.dumps({"type": "token", "content": delta}) + "\n"
                if chunk.get("done"):
                    full_response = "".join(assistant_chunks).strip()
                    if full_response:
                        assistant_message = Message(
                            conversation_id=conversation.id,
                            role="assistant",
                            content=full_response,
                        )
                        conversation.updated_at = datetime.utcnow()
                        db.add(assistant_message)
                        db.add(conversation)
                        db.commit()
                    yield json.dumps({"type": "done"}) + "\n"
                    return
        except httpx.HTTPError as exc:
            db.rollback()
            message = f"Model service connection failed. Check service URL, API key, and model name. Details: {exc}"
            yield json.dumps({"type": "error", "message": message}) + "\n"
            return
        except Exception as exc:  # pragma: no cover
            db.rollback()
            yield json.dumps({"type": "error", "message": str(exc)}) + "\n"
            return

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
