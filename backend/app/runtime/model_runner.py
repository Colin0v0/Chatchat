from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from ..chat.types import ChatMessagePayload
from ..llm.thinking import ThinkTagStreamNormalizer, inject_thinking_system_prompt
from ..providers import provider_registry, resolve_model_profile, resolve_reasoning_profile
from ..providers.base import ProviderStreamRequest
from .text_utils import coalesce_leading_system_messages, strip_loose_think_tags


@dataclass(frozen=True)
class ModelStreamChunk:
    output_text_delta: str = ""
    reasoning_delta: str = ""
    done: bool = False


async def stream_model_response(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    temperature: float | None = None,
    requested_reasoning: bool | None = None,
    requested_reasoning_profile: str | None = None,
) -> AsyncIterator[ModelStreamChunk]:
    profile = resolve_model_profile(model)
    if profile is None:
        raise ValueError(f"Model is not enabled in catalog: {model}")

    reasoning_profile = resolve_reasoning_profile(
        model,
        requested_reasoning,
        requested_profile=requested_reasoning_profile,
    )
    normalized_history = coalesce_leading_system_messages(messages)
    model_messages = inject_thinking_system_prompt(
        model=model,
        messages=normalized_history,
        reasoning_profile=reasoning_profile,
        reasoning_visibility=profile.capabilities.reasoning_visibility,
    )

    show_reasoning = reasoning_profile != "off"
    think_normalizer = ThinkTagStreamNormalizer(emit_reasoning=show_reasoning)
    adapter = provider_registry.get(profile.provider_family)

    async for event in adapter.stream(
        ProviderStreamRequest(
            profile=profile,
            messages=model_messages,
            reasoning_profile=reasoning_profile,
            temperature=temperature,
        )
    ):
        if event.kind == "reasoning_delta":
            reasoning_delta = str(event.payload.get("content", "") or "")
            if reasoning_delta:
                yield ModelStreamChunk(reasoning_delta=reasoning_delta)
            continue

        if event.kind == "output_text_delta":
            raw_delta = str(event.payload.get("content", "") or "")
            normalized_reasoning, normalized_answer = think_normalizer.feed(raw_delta)
            if normalized_reasoning and show_reasoning:
                yield ModelStreamChunk(reasoning_delta=normalized_reasoning)
            if normalized_answer:
                clean_answer = strip_loose_think_tags(normalized_answer)
                if clean_answer:
                    yield ModelStreamChunk(output_text_delta=clean_answer)
            continue

        if event.kind == "completed":
            tail_reasoning, tail_answer = think_normalizer.flush()
            if tail_reasoning and show_reasoning:
                yield ModelStreamChunk(reasoning_delta=tail_reasoning)
            if tail_answer:
                clean_tail = strip_loose_think_tags(tail_answer)
                if clean_tail:
                    yield ModelStreamChunk(output_text_delta=clean_tail)
            yield ModelStreamChunk(done=True)
            break


async def complete_model_response(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    temperature: float | None = None,
    requested_reasoning: bool | None = None,
    requested_reasoning_profile: str | None = None,
) -> str:
    answer_chunks: list[str] = []
    async for chunk in stream_model_response(
        model=model,
        messages=messages,
        temperature=temperature,
        requested_reasoning=requested_reasoning,
        requested_reasoning_profile=requested_reasoning_profile,
    ):
        if chunk.output_text_delta:
            answer_chunks.append(chunk.output_text_delta)
    return "".join(answer_chunks).strip()
