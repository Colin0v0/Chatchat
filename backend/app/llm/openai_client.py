from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from ..chat.types import ChatMessagePayload
from ..core.config import settings
from .capabilities import (
    DiscoveredModel,
    filter_chat_model_names,
    namespaced_model,
    normalize_base_url,
    parse_openai_allowlist,
    parse_openai_vision_allowlist,
)


def openai_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if settings.openai_api_key:
        headers["Authorization"] = f"Bearer {settings.openai_api_key}"
    return headers


async def list_openai_models() -> list[DiscoveredModel]:
    allowlist = parse_openai_allowlist()
    vision_models = parse_openai_vision_allowlist()
    try:
        async with httpx.AsyncClient(
            base_url=normalize_base_url(settings.openai_base_url),
            timeout=10.0,
            headers=openai_headers(),
        ) as client:
            response = await client.get("/models")
            response.raise_for_status()
    except httpx.HTTPError:
        return [
            DiscoveredModel(
                id=namespaced_model("openai", model),
                supports_image_input=model in vision_models,
            )
            for model in filter_chat_model_names(allowlist)
        ]

    payload = response.json()
    models = [item.get("id", "") for item in payload.get("data", []) if item.get("id")]
    if allowlist:
        allowed = set(allowlist)
        models = [model for model in models if model in allowed]
    models = filter_chat_model_names(models)
    return [
        DiscoveredModel(
            id=namespaced_model("openai", model),
            supports_image_input=model in vision_models,
        )
        for model in models
    ]


def openai_message_payload(message: ChatMessagePayload) -> dict[str, object]:
    if not message.images:
        return {
            "role": message.role,
            "content": message.content,
        }

    content: list[dict[str, object]] = [{"type": "text", "text": message.content}]
    content.extend(
        {
            "type": "image_url",
            "image_url": {"url": image.data_url},
        }
        for image in message.images
    )
    return {
        "role": message.role,
        "content": content,
    }


async def stream_openai_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
) -> AsyncIterator[dict]:
    payload = {
        "model": model,
        "messages": [openai_message_payload(message) for message in messages],
        "stream": True,
    }

    timeout = httpx.Timeout(settings.request_timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(
        base_url=normalize_base_url(settings.openai_base_url),
        timeout=timeout,
        headers=openai_headers(),
    ) as client:
        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for raw_line in response.aiter_lines():
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line[5:].strip()
                if not line:
                    continue
                if line == "[DONE]":
                    yield {"done": True}
                    return

                chunk = json.loads(line)
                choices = chunk.get("choices") or []
                if not choices:
                    continue

                choice = choices[0]
                delta = choice.get("delta", {}).get("content", "")
                reasoning_delta = choice.get("delta", {}).get("reasoning_content", "")
                finish_reason = choice.get("finish_reason")

                event: dict[str, object] = {}
                if delta:
                    event["message"] = {"content": delta}
                if reasoning_delta:
                    event["reasoning"] = {"content": reasoning_delta}
                if finish_reason is not None:
                    event["done"] = True

                if event:
                    yield event
