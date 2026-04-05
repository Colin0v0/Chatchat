from __future__ import annotations

import asyncio
import base64
import io
import json
import time
from collections.abc import AsyncIterator

import httpx
from PIL import Image

from ..chat.types import ChatImagePayload, ChatMessagePayload
from ..core.config import settings
from .ollama_runtime import log_ollama_request, ollama_keep_alive_value
from .capabilities import (
    DiscoveredModel,
    OLLAMA_CAPABILITY_CACHE,
    filter_chat_model_names,
    namespaced_model,
    normalize_base_url,
)


async def fetch_ollama_capabilities(model_name: str) -> set[str]:
    async with httpx.AsyncClient(
        base_url=normalize_base_url(settings.ollama_base_url),
        timeout=10.0,
    ) as client:
        response = await client.post("/api/show", json={"model": model_name})
        response.raise_for_status()
        payload = response.json()
    capabilities = payload.get("capabilities") or []
    return {str(item).strip().lower() for item in capabilities if str(item).strip()}


async def list_ollama_models() -> list[DiscoveredModel]:
    try:
        async with httpx.AsyncClient(
            base_url=normalize_base_url(settings.ollama_base_url),
            timeout=10.0,
        ) as client:
            response = await client.get("/api/tags")
            response.raise_for_status()
    except httpx.HTTPError:
        return []

    payload = response.json()
    model_names = [item["name"] for item in payload.get("models", []) if item.get("name")]
    denylist = {
        name.strip().lower()
        for name in settings.ollama_model_denylist.split(",")
        if name.strip()
    }
    if denylist:
        model_names = [name for name in model_names if name.strip().lower() not in denylist]
    chat_model_names = filter_chat_model_names(model_names)
    capability_results = await asyncio.gather(
        *[fetch_ollama_capabilities(name) for name in chat_model_names],
        return_exceptions=True,
    )

    discovered: list[DiscoveredModel] = []
    for model_name, capability_result in zip(chat_model_names, capability_results, strict=False):
        capabilities = set()
        if not isinstance(capability_result, Exception):
            capabilities = capability_result
        OLLAMA_CAPABILITY_CACHE[model_name] = capabilities
        discovered.append(
            DiscoveredModel(
                id=namespaced_model("ollama", model_name),
                supports_image_input="vision" in capabilities,
                supports_thinking="thinking" in capabilities,
            )
        )
    return discovered


def ollama_supports_thinking(model_name: str) -> bool:
    return "thinking" in OLLAMA_CAPABILITY_CACHE.get(model_name, set())


def ollama_image_base64(image: ChatImagePayload) -> str:
    encoded = image.data_url.split(",", 1)[1]
    if image.mime_type == "image/jpeg":
        return encoded

    raw = base64.b64decode(encoded)
    with Image.open(io.BytesIO(raw)) as decoded:
        frame = decoded.convert("RGB")
        buffer = io.BytesIO()
        frame.save(buffer, format="JPEG", quality=92)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def ollama_message_payload(message: ChatMessagePayload) -> dict[str, object]:
    payload: dict[str, object] = {
        "role": message.role,
        "content": message.content,
    }
    if message.images:
        payload["images"] = [ollama_image_base64(image) for image in message.images]
    return payload


async def stream_ollama_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    thinking_enabled: bool | None = None,
    base_url_override: str | None = None,
    context_window: int | None = None,
) -> AsyncIterator[dict]:
    keep_alive = ollama_keep_alive_value(settings.ollama_keep_alive_seconds)
    payload = {
        "model": model,
        "messages": [ollama_message_payload(message) for message in messages],
        "stream": True,
        "keep_alive": keep_alive,
    }
    if ollama_supports_thinking(model):
        payload["think"] = True if thinking_enabled is None else thinking_enabled
    if isinstance(context_window, int) and context_window > 0:
        payload["options"] = {"num_ctx": context_window}

    timeout = httpx.Timeout(settings.request_timeout_seconds, connect=10.0)
    started_at = time.perf_counter()
    async with httpx.AsyncClient(
        base_url=normalize_base_url(base_url_override or settings.ollama_base_url),
        timeout=timeout,
    ) as client:
        async with client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                event: dict[str, object] = {}
                thinking_delta = chunk.get("message", {}).get("thinking", "")
                if thinking_delta:
                    event["reasoning"] = {"content": thinking_delta}

                content_delta = chunk.get("message", {}).get("content", "")
                if content_delta:
                    event["message"] = {"content": content_delta}

                if chunk.get("done"):
                    log_ollama_request(
                        kind="chat",
                        model=model,
                        keep_alive=keep_alive,
                        started_at=started_at,
                        response_payload=chunk,
                    )
                    event["done"] = True

                if event:
                    yield event
