from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import ANY

import pytest
from fastapi import HTTPException

from app.application import chat_preparation
from app.application.chat_requests import RegenerationSource
from app.schemas import RegenerateRequest
from app.storage.models import Conversation, Message


def _profile(model_id: str = "chat-model", *, input_image: bool = True):
    return SimpleNamespace(
        id=model_id,
        capabilities=SimpleNamespace(
            input_image=input_image,
            input_pdf=True,
            input_other_file=True,
        ),
    )


def test_ensure_uploads_supported_by_model_rejects_images_when_model_disallows_them():
    upload = SimpleNamespace(filename="picture.png", content_type="image/png")

    with pytest.raises(HTTPException) as exc:
        chat_preparation._ensure_uploads_supported_by_model(
            profile=_profile(input_image=False),
            uploads=[upload],
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "The selected model does not support image uploads."


@pytest.mark.anyio
async def test_prepare_regeneration_run_request_coordinates_dependencies(monkeypatch):
    conversation = Conversation(id=8, model="test-model")
    source_user = Message(id=3, conversation_id=8, role="user", content="retry this")
    regenerated_user = Message(id=4, conversation_id=8, role="user", content="retry this")
    regeneration = RegenerationSource(
        source_user=source_user,
        history_messages=[source_user],
    )
    built_run_request = SimpleNamespace(kind="run-request")
    resolved_profile = _profile("new-model")
    captured: dict[str, object] = {}

    monkeypatch.setattr(chat_preparation, "load_user_chat_conversation", lambda **kwargs: conversation)

    def fake_ensure_conversation_run_model(**kwargs):
        captured["model_sync"] = kwargs

    def fake_resolve_regeneration_source(**kwargs):
        captured["regeneration"] = kwargs
        return regeneration

    def fake_persist_regenerated_turn(**kwargs):
        captured["persist"] = kwargs
        return regenerated_user

    def fake_build_chat_run_request(**kwargs):
        captured["build"] = kwargs
        return built_run_request

    async def fake_ensure_no_active_chat_run(**kwargs):
        captured["active_check"] = kwargs

    monkeypatch.setattr(chat_preparation, "_ensure_no_active_chat_run", fake_ensure_no_active_chat_run)
    monkeypatch.setattr(chat_preparation, "ensure_conversation_run_model", fake_ensure_conversation_run_model)
    monkeypatch.setattr(chat_preparation, "resolve_chat_model", lambda **kwargs: resolved_profile)
    monkeypatch.setattr(chat_preparation, "resolve_regeneration_source", fake_resolve_regeneration_source)
    monkeypatch.setattr(chat_preparation, "persist_regenerated_turn", fake_persist_regenerated_turn)
    monkeypatch.setattr(chat_preparation, "build_chat_run_request", fake_build_chat_run_request)

    payload = RegenerateRequest(
        conversation_id=8,
        assistant_message_id=99,
        edited_content="  revised prompt  ",
        model="new-model",
        tool_mode="knowledge",
        reasoning_profile="high",
    )
    services = SimpleNamespace()
    request = SimpleNamespace()
    db = SimpleNamespace()
    result = await chat_preparation.prepare_regeneration_run_request(
        current_user=SimpleNamespace(id=7),
        services=services,
        payload=payload,
        request=request,
        db=db,
    )

    assert result is built_run_request
    assert captured["active_check"] == {
        "request": request,
        "conversation_id": 8,
    }
    assert captured["model_sync"] == {
        "db": db,
        "conversation": conversation,
        "requested_model": "new-model",
    }
    assert captured["regeneration"] == {
        "conversation": conversation,
        "assistant_message_id": 99,
    }
    assert captured["persist"] == {
        "db": db,
        "conversation": conversation,
        "source_user": source_user,
        "override_content": "revised prompt",
    }
    assert captured["build"] == {
        "services": services,
        "request": request,
        "conversation": conversation,
        "user_message": regenerated_user,
        "history_messages": [source_user],
        "query": "revised prompt",
        "temperature": None,
        "tool_mode": "knowledge",
        "reasoning_profile": "high",
        "knowledge_folders": [],
    }


@pytest.mark.anyio
async def test_prepare_chat_stream_run_request_coordinates_submission_dependencies(monkeypatch):
    existing_conversation = Conversation(id=5, model="existing-model")
    persisted_conversation = Conversation(id=5, model="chat-model")
    persisted_message = Message(id=21, conversation_id=5, role="user", content="Hello")
    reloaded_conversation = Conversation(id=5, model="chat-model")
    reloaded_conversation.messages = [persisted_message]
    built_run_request = SimpleNamespace(kind="run-request")
    uploaded_attachment = SimpleNamespace(relative_path="uploads/test.txt")
    captured: dict[str, object] = {}
    current_user = SimpleNamespace(id=9)
    services = SimpleNamespace()
    request = SimpleNamespace()
    db = SimpleNamespace()
    upload_file = SimpleNamespace(filename="test.txt", content_type="text/plain")
    resolved_profile = _profile()

    def fake_resolve_chat_model(**kwargs):
        captured["profile"] = kwargs
        return resolved_profile

    monkeypatch.setattr(chat_preparation, "resolve_chat_model", fake_resolve_chat_model)
    monkeypatch.setattr(chat_preparation, "load_user_chat_conversation", lambda **kwargs: existing_conversation)

    async def fake_persist_uploaded_attachments(uploads):
        captured["uploads"] = uploads
        return [uploaded_attachment]

    def fake_persist_chat_turn(**kwargs):
        captured["persist"] = kwargs
        return SimpleNamespace(conversation=persisted_conversation, user_message=persisted_message)

    def fake_reload_conversation_for_run(**kwargs):
        captured["reload"] = kwargs
        return reloaded_conversation

    def fake_build_chat_run_request(**kwargs):
        captured["build"] = kwargs
        return built_run_request

    async def fake_ensure_no_active_chat_run(**kwargs):
        captured["active_check"] = kwargs

    monkeypatch.setattr(chat_preparation, "_ensure_no_active_chat_run", fake_ensure_no_active_chat_run)
    monkeypatch.setattr(chat_preparation, "persist_uploaded_attachments", fake_persist_uploaded_attachments)
    monkeypatch.setattr(chat_preparation, "persist_chat_turn", fake_persist_chat_turn)
    monkeypatch.setattr(chat_preparation, "reload_conversation_for_run", fake_reload_conversation_for_run)
    monkeypatch.setattr(chat_preparation, "build_chat_run_request", fake_build_chat_run_request)

    result = await chat_preparation.prepare_chat_stream_run_request(
        current_user=current_user,
        services=services,
        request=request,
        db=db,
        conversation_id=5,
        message="  Hello  ",
        model="chat-model",
        temperature=0.4,
        tool_mode="search",
        reasoning_profile="medium",
        knowledge_folders=[],
        files=[upload_file],
    )

    assert result is built_run_request
    assert captured["active_check"] == {
        "request": request,
        "conversation_id": 5,
    }
    assert captured["profile"] == {
        "requested_model": "chat-model",
        "fallback_model": chat_preparation.settings.default_model,
    }
    assert captured["uploads"] == [upload_file]
    assert captured["persist"] == {
        "db": db,
        "current_user": current_user,
        "conversation": existing_conversation,
        "profile": resolved_profile,
        "content": "Hello",
        "uploaded_attachments": [uploaded_attachment],
        "temporary_chat": False,
    }
    assert captured["reload"] == {
        "db": db,
        "conversation_id": 5,
    }
    assert captured["build"] == {
        "services": services,
        "request": request,
        "conversation": reloaded_conversation,
        "user_message": persisted_message,
        "history_messages": [persisted_message],
        "query": "Hello",
        "temperature": 0.4,
        "tool_mode": "search",
        "reasoning_profile": "medium",
        "knowledge_folders": [],
    }


@pytest.mark.anyio
async def test_prepare_chat_stream_run_request_rejects_empty_message_without_uploads():
    with pytest.raises(HTTPException) as exc:
        await chat_preparation.prepare_chat_stream_run_request(
            current_user=SimpleNamespace(id=9),
            services=SimpleNamespace(),
            request=SimpleNamespace(),
            db=SimpleNamespace(),
            conversation_id=None,
            message="   ",
            model=None,
            temperature=None,
            tool_mode="none",
            reasoning_profile=None,
            knowledge_folders=[],
            files=None,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Message cannot be empty"
