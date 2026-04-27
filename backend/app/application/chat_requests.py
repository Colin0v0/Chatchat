from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from ..chat.context import conversation_options, history_message_ids
from ..chat.state import ChatServices
from ..runtime.requests import ChatRunRequest
from ..schemas import ReasoningProfileValue, ToolMode
from ..storage.access import get_user_conversation
from ..storage.models import Conversation, Message
from ..tools.policy import build_tool_policy
from .chat_turns import resolve_chat_model


@dataclass(frozen=True)
class RegenerationSource:
    source_user: Message
    history_messages: list[Message]


def load_user_chat_conversation(
    *,
    db: Session,
    conversation_id: int,
    user_id: int,
) -> Conversation:
    conversation = get_user_conversation(
        db,
        conversation_id=conversation_id,
        user_id=user_id,
        options=conversation_options(),
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


def ensure_conversation_run_model(
    *,
    db: Session,
    conversation: Conversation,
    requested_model: str | None,
) -> None:
    profile = resolve_chat_model(
        requested_model=requested_model or conversation.model,
        fallback_model=conversation.model,
    )
    if requested_model is None or conversation.model == profile.id:
        return
    conversation.model = profile.id
    db.add(conversation)
    db.commit()
    db.refresh(conversation)


def resolve_regeneration_source(
    *,
    conversation: Conversation,
    assistant_message_id: int,
) -> RegenerationSource:
    target_index = next(
        (
            index
            for index, message in enumerate(conversation.messages)
            if message.id == assistant_message_id and message.role == "assistant"
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

    return RegenerationSource(
        source_user=source_user,
        history_messages=list(conversation.messages[:target_index]),
    )


def reload_conversation_for_run(
    *,
    db: Session,
    conversation_id: int,
) -> Conversation:
    conversation = db.get(
        Conversation,
        conversation_id,
        options=conversation_options(),
    )
    if conversation is None:
        raise RuntimeError("Conversation not found after persisting chat turn.")
    return conversation


def build_chat_run_request(
    *,
    services: ChatServices,
    request: Request,
    conversation: Conversation,
    user_message: Message,
    history_messages: list[Message],
    query: str,
    tool_mode: ToolMode,
    knowledge_folders: list[str],
    reasoning_profile: ReasoningProfileValue | None,
) -> ChatRunRequest:
    return ChatRunRequest(
        services=services,
        request=request,
        conversation_id=conversation.id,
        message_id=user_message.id,
        model=conversation.model,
        history_message_ids=history_message_ids(history_messages),
        query=query,
        tool_policy=build_tool_policy(tool_mode, knowledge_folders=knowledge_folders),
        requested_reasoning_profile=reasoning_profile,
    )
