from __future__ import annotations

from collections.abc import AsyncIterator

from ..chat.types import ChatMessagePayload
from .capabilities import model_provider_and_name
from .ollama_client import stream_ollama_chat
from .openai_client import stream_openai_chat


async def stream_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    thinking_enabled: bool | None = None,
) -> AsyncIterator[dict]:
    provider, model_name = model_provider_and_name(model)
    if provider == "openai":
        async for chunk in stream_openai_chat(model=model_name, messages=messages):
            yield chunk
        return

    async for chunk in stream_ollama_chat(
        model=model_name,
        messages=messages,
        thinking_enabled=thinking_enabled,
    ):
        yield chunk


async def complete_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    thinking_enabled: bool | None = None,
) -> str:
    chunks: list[str] = []
    async for chunk in stream_chat(
        model=model,
        messages=messages,
        thinking_enabled=thinking_enabled,
    ):
        delta = chunk.get("message", {}).get("content", "")
        if delta:
            chunks.append(delta)
    return "".join(chunks).strip()
