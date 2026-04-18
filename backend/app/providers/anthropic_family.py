from __future__ import annotations

from collections.abc import AsyncIterator

from ..provider_transports.anthropic import stream_claude_chat
from ..runtime.events import CanonicalEvent, completed_event, output_text_delta_event, reasoning_delta_event
from .base import ProviderAdapter, ProviderStreamRequest


class AnthropicProviderAdapter(ProviderAdapter):
    family = "anthropic"

    async def stream(self, request: ProviderStreamRequest) -> AsyncIterator[CanonicalEvent]:
        async for chunk in stream_claude_chat(
            model=request.profile.upstream_model,
            messages=request.messages,
            reasoning_profile=request.reasoning_profile,
            base_url_override=request.profile.chat_base_url,
            api_key_override=request.profile.api_key,
        ):
            reasoning_delta = str(chunk.get("reasoning", {}).get("content", "") or "")
            if reasoning_delta:
                yield reasoning_delta_event(reasoning_delta)

            text_delta = str(chunk.get("message", {}).get("content", "") or "")
            if text_delta:
                yield output_text_delta_event(text_delta)

            if chunk.get("done"):
                yield completed_event()
