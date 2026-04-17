from __future__ import annotations

from collections.abc import AsyncIterator

from ..chat.types import ChatMessagePayload
from ..core.config import settings
from .capabilities import model_provider_and_name
from .capabilities import normalize_model as normalize_model_id
from .catalog import resolve_effective_thinking, resolve_model_route
from .claude_client import complete_claude_chat, stream_claude_chat
from .gemini_client import stream_gemini_chat
from .ollama_client import stream_ollama_chat
from .openai_client import stream_openai_chat


async def stream_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    thinking_enabled: bool | None = None,
) -> AsyncIterator[dict]:
    route = resolve_model_route(model)
    if settings.model_catalog_strict and route is None:
        raise ValueError(
            f"Model is not enabled in catalog: {normalize_model_id(model)}"
        )

    effective_thinking = resolve_effective_thinking(
        model,
        thinking_enabled,
        thinking_mode=route["thinking_mode"] if route else None,
    )
    base_url_override = None
    if route:
        provider = route["provider"]
        model_name = route["upstream_model"]
        if route["native_multimodal"] == "local":
            base_url_override = route["upstream_service_base_url"]
            if not base_url_override:
                raise RuntimeError(f"Native multimodal endpoint is not configured for model: {model}")
        else:
            base_url_override = route["base_url"]
    else:
        provider, model_name = model_provider_and_name(model)

    if provider == "gemini":
        async for chunk in stream_gemini_chat(
            model=model_name,
            messages=messages,
            base_url_override=base_url_override,
            api_key_override=route["api_key"] if route else None,
        ):
            yield chunk
        return

    if provider == "claude":
        async for chunk in stream_claude_chat(
            model=model_name,
            messages=messages,
            base_url_override=base_url_override,
            api_key_override=route["api_key"] if route else None,
        ):
            yield chunk
        return

    if provider in ("openai", "openai_local", "codex", "trio"):
        async for chunk in stream_openai_chat(
            model=model_name,
            messages=messages,
            provider=provider,
            thinking_enabled=effective_thinking,
            base_url_override=base_url_override,
            api_key_override=route["api_key"] if route else None,
        ):
            yield chunk
        return

    async for chunk in stream_ollama_chat(
        model=model_name,
        messages=messages,
        thinking_enabled=effective_thinking,
        base_url_override=base_url_override,
        context_window=route["context_window"] if route else None,
    ):
        yield chunk


async def complete_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    thinking_enabled: bool | None = None,
) -> str:
    route = resolve_model_route(model)
    if route and route["provider"] == "claude":
        chunks: list[str] = []
        async for chunk in complete_claude_chat(
            model=route["upstream_model"],
            messages=messages,
            base_url_override=route["base_url"],
            api_key_override=route["api_key"],
        ):
            delta = chunk.get("message", {}).get("content", "")
            if delta:
                chunks.append(delta)
        return "".join(chunks).strip()

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
