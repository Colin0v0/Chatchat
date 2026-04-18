from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.application import chat_requests
from app.application.chat_requests import (
    build_chat_run_request,
    ensure_conversation_run_model,
    load_user_chat_conversation,
    resolve_regeneration_source,
)
from app.storage.models import Conversation, Message


def test_load_user_chat_conversation_returns_owned_conversation(monkeypatch):
    conversation = Conversation(id=9, model="test-model")
    monkeypatch.setattr(chat_requests, "get_user_conversation", lambda *args, **kwargs: conversation)

    loaded = load_user_chat_conversation(
        db=SimpleNamespace(),
        conversation_id=9,
        user_id=3,
    )

    assert loaded is conversation


def test_load_user_chat_conversation_raises_when_missing(monkeypatch):
    monkeypatch.setattr(chat_requests, "get_user_conversation", lambda *args, **kwargs: None)

    with pytest.raises(HTTPException) as exc:
        load_user_chat_conversation(
            db=SimpleNamespace(),
            conversation_id=9,
            user_id=3,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Conversation not found"


def test_resolve_regeneration_source_returns_prior_user_and_history_slice():
    conversation = Conversation(id=7, model="test-model")
    first_user = Message(id=1, conversation_id=7, role="user", content="hello")
    first_assistant = Message(id=2, conversation_id=7, role="assistant", content="hi")
    second_user = Message(id=3, conversation_id=7, role="user", content="retry this")
    second_assistant = Message(id=4, conversation_id=7, role="assistant", content="answer")
    conversation.messages = [first_user, first_assistant, second_user, second_assistant]

    result = resolve_regeneration_source(conversation=conversation, assistant_message_id=4)

    assert result.source_user is second_user
    assert [message.id for message in result.history_messages] == [1, 2, 3]


def test_resolve_regeneration_source_requires_target_assistant_message():
    conversation = Conversation(id=7, model="test-model")
    conversation.messages = [Message(id=1, conversation_id=7, role="user", content="hello")]

    with pytest.raises(HTTPException) as exc:
        resolve_regeneration_source(conversation=conversation, assistant_message_id=999)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Assistant message not found"


def test_resolve_regeneration_source_requires_prior_user_message():
    conversation = Conversation(id=7, model="test-model")
    conversation.messages = [Message(id=2, conversation_id=7, role="assistant", content="lonely answer")]

    with pytest.raises(HTTPException) as exc:
        resolve_regeneration_source(conversation=conversation, assistant_message_id=2)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Source user message not found"


def test_build_chat_run_request_encodes_history_and_tool_policy():
    conversation = Conversation(id=12, model="openai:gpt-5")
    history = [
        Message(id=1, conversation_id=12, role="user", content="q1"),
        Message(id=2, conversation_id=12, role="assistant", content="a1"),
    ]
    user_message = Message(id=3, conversation_id=12, role="user", content="q2")

    run_request = build_chat_run_request(
        services=SimpleNamespace(),
        request=SimpleNamespace(),
        conversation=conversation,
        user_message=user_message,
        history_messages=history,
        query="q2",
        tool_mode="search",
        reasoning_profile="high",
    )

    assert run_request.conversation_id == 12
    assert run_request.message_id == 3
    assert run_request.model == "openai:gpt-5"
    assert run_request.history_message_ids == [1, 2]
    assert run_request.query == "q2"
    assert run_request.tool_policy.mode == "search"
    assert run_request.tool_policy.source_mode == "search"
    assert run_request.requested_reasoning_profile == "high"


def test_ensure_conversation_run_model_persists_requested_model_change(monkeypatch):
    conversation = Conversation(id=5, model="old-model")
    db = SimpleNamespace(added=[], commit_count=0, refresh_count=0)

    def add(item):
        db.added.append(item)

    def commit():
        db.commit_count += 1

    def refresh(item):
        db.refresh_count += 1

    db.add = add
    db.commit = commit
    db.refresh = refresh
    monkeypatch.setattr(chat_requests, "resolve_chat_model", lambda **_: SimpleNamespace(id="new-model"))

    ensure_conversation_run_model(
        db=db,
        conversation=conversation,
        requested_model="new-model",
    )

    assert conversation.model == "new-model"
    assert db.added == [conversation]
    assert db.commit_count == 1
    assert db.refresh_count == 1


def test_ensure_conversation_run_model_only_validates_when_model_not_changed(monkeypatch):
    conversation = Conversation(id=5, model="same-model")
    db = SimpleNamespace(added=[], commit_count=0, refresh_count=0)
    db.add = lambda item: db.added.append(item)
    db.commit = lambda: setattr(db, "commit_count", db.commit_count + 1)
    db.refresh = lambda item: setattr(db, "refresh_count", db.refresh_count + 1)
    monkeypatch.setattr(chat_requests, "resolve_chat_model", lambda **_: SimpleNamespace(id="same-model"))

    ensure_conversation_run_model(
        db=db,
        conversation=conversation,
        requested_model=None,
    )

    assert conversation.model == "same-model"
    assert db.added == []
    assert db.commit_count == 0
    assert db.refresh_count == 0
