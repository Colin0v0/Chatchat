from __future__ import annotations

import asyncio
import base64
import io
import json
from collections.abc import AsyncIterator
from typing import Literal, TypedDict

import httpx
from PIL import Image

from .chat_types import ChatImagePayload, ChatMessagePayload
from .config import settings

Provider = Literal["ollama", "openai"]


class DiscoveredModel(TypedDict):
    id: str
    supports_image_input: bool


class ModelOption(TypedDict):
    id: str
    label: str
    supports_thinking: bool
    supports_thinking_trace: bool
    supports_image_input: bool
    supports_image_upload: bool
    chat_model: str | None
    reasoning_model: str | None


EMBEDDING_MODEL_HINTS = (
    "embed",
    "embedding",
    "nomic-embed",
    "mxbai-embed",
    "bge-",
    "e5-",
)
NON_CHAT_MODEL_HINTS = (
    "translategemma",
    "translation",
)
OLLAMA_CAPABILITY_CACHE: dict[str, set[str]] = {}


def _normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def _parse_csv_allowlist(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_openai_allowlist() -> list[str]:
    return _parse_csv_allowlist(settings.openai_model_allowlist)


def _parse_openai_vision_allowlist() -> set[str]:
    return set(_parse_csv_allowlist(settings.openai_vision_model_allowlist))


def _is_embedding_model_name(model_name: str) -> bool:
    normalized = model_name.strip().lower()
    return any(hint in normalized for hint in EMBEDDING_MODEL_HINTS)


def _is_non_chat_model_name(model_name: str) -> bool:
    normalized = model_name.strip().lower()
    return any(hint in normalized for hint in NON_CHAT_MODEL_HINTS)


def _filter_chat_model_names(model_names: list[str]) -> list[str]:
    return [
        name
        for name in model_names
        if not _is_embedding_model_name(name) and not _is_non_chat_model_name(name)
    ]


def model_provider_and_name(model: str) -> tuple[Provider, str]:
    parts = model.split(":", 1)
    if len(parts) == 2 and parts[0] in ("ollama", "openai") and parts[1].strip():
        return parts[0], parts[1].strip()
    if len(parts) == 2 and parts[0] not in ("ollama", "openai"):
        return "ollama", model

    if settings.default_provider == "openai":
        return "openai", model
    return "ollama", model


def namespaced_model(provider: Provider, model_name: str) -> str:
    return f"{provider}:{model_name}"


def normalize_model(model: str) -> str:
    provider, model_name = model_provider_and_name(model)
    return namespaced_model(provider, model_name)


def present_model_name(model: str) -> str:
    provider, model_name = model_provider_and_name(model)
    if provider in ("ollama", "openai"):
        return model_name
    return model


def supports_native_image_input(model: str) -> bool:
    provider, model_name = model_provider_and_name(model)
    if provider == "openai":
        return model_name in _parse_openai_vision_allowlist()
    return "vision" in OLLAMA_CAPABILITY_CACHE.get(model_name, set())


def build_model_options(models: list[DiscoveredModel]) -> list[ModelOption]:
    unique_models = list(dict.fromkeys(item["id"] for item in models))
    discovered_by_id = {item["id"]: item for item in models}
    available = set(unique_models)

    deepseek_chat = namespaced_model("openai", "deepseek-chat")
    deepseek_reasoner = namespaced_model("openai", "deepseek-reasoner")
    reasoning_pairs: dict[str, tuple[str, str]] = {}
    reasoning_trace_models: set[str] = set()

    if deepseek_chat in available and deepseek_reasoner in available:
        reasoning_pairs[deepseek_chat] = (deepseek_chat, deepseek_reasoner)
        reasoning_pairs[deepseek_reasoner] = (deepseek_chat, deepseek_reasoner)
        reasoning_trace_models.add(deepseek_reasoner)

    options: list[ModelOption] = []
    for model in unique_models:
        pair = reasoning_pairs.get(model)
        chat_model = pair[0] if pair else None
        reasoning_model = pair[1] if pair else None
        supports_image_input = discovered_by_id.get(model, {}).get("supports_image_input", False)
        options.append(
            ModelOption(
                id=model,
                label=present_model_name(model),
                supports_thinking=pair is not None,
                supports_thinking_trace=model in reasoning_trace_models,
                supports_image_input=supports_image_input,
                supports_image_upload=True,
                chat_model=chat_model,
                reasoning_model=reasoning_model,
            )
        )

    return options


async def _fetch_ollama_capabilities(model_name: str) -> set[str]:
    async with httpx.AsyncClient(
        base_url=_normalize_base_url(settings.ollama_base_url),
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
            base_url=_normalize_base_url(settings.ollama_base_url),
            timeout=10.0,
        ) as client:
            response = await client.get("/api/tags")
            response.raise_for_status()
    except httpx.HTTPError:
        return []

    payload = response.json()
    model_names = [item["name"] for item in payload.get("models", []) if item.get("name")]
    chat_model_names = _filter_chat_model_names(model_names)
    capability_results = await asyncio.gather(
        *[_fetch_ollama_capabilities(name) for name in chat_model_names],
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
            )
        )
    return discovered


def _openai_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if settings.openai_api_key:
        headers["Authorization"] = f"Bearer {settings.openai_api_key}"
    return headers


async def list_openai_models() -> list[DiscoveredModel]:
    allowlist = _parse_openai_allowlist()
    vision_models = _parse_openai_vision_allowlist()
    try:
        async with httpx.AsyncClient(
            base_url=_normalize_base_url(settings.openai_base_url),
            timeout=10.0,
            headers=_openai_headers(),
        ) as client:
            response = await client.get("/models")
            response.raise_for_status()
    except httpx.HTTPError:
        return [
            DiscoveredModel(
                id=namespaced_model("openai", model),
                supports_image_input=model in vision_models,
            )
            for model in _filter_chat_model_names(allowlist)
        ]

    payload = response.json()
    models = [item.get("id", "") for item in payload.get("data", []) if item.get("id")]
    if allowlist:
        allowed = set(allowlist)
        models = [model for model in models if model in allowed]
    models = _filter_chat_model_names(models)
    return [
        DiscoveredModel(
            id=namespaced_model("openai", model),
            supports_image_input=model in vision_models,
        )
        for model in models
    ]


def _ollama_image_base64(image: ChatImagePayload) -> str:
    encoded = image.data_url.split(",", 1)[1]
    if image.mime_type == "image/jpeg":
        return encoded

    raw = base64.b64decode(encoded)
    with Image.open(io.BytesIO(raw)) as decoded:
        frame = decoded.convert("RGB")
        buffer = io.BytesIO()
        frame.save(buffer, format="JPEG", quality=92)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _ollama_message_payload(message: ChatMessagePayload) -> dict[str, object]:
    payload: dict[str, object] = {
        "role": message.role,
        "content": message.content,
    }
    if message.images:
        payload["images"] = [_ollama_image_base64(image) for image in message.images]
    return payload


async def stream_ollama_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
) -> AsyncIterator[dict]:
    payload = {
        "model": model,
        "messages": [_ollama_message_payload(message) for message in messages],
        "stream": True,
    }

    timeout = httpx.Timeout(settings.request_timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(
        base_url=_normalize_base_url(settings.ollama_base_url),
        timeout=timeout,
    ) as client:
        async with client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                yield json.loads(line)


def _openai_message_payload(message: ChatMessagePayload) -> dict[str, object]:
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
        "messages": [_openai_message_payload(message) for message in messages],
        "stream": True,
    }

    timeout = httpx.Timeout(settings.request_timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(
        base_url=_normalize_base_url(settings.openai_base_url),
        timeout=timeout,
        headers=_openai_headers(),
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


async def stream_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
) -> AsyncIterator[dict]:
    provider, model_name = model_provider_and_name(model)
    if provider == "openai":
        async for chunk in stream_openai_chat(model=model_name, messages=messages):
            yield chunk
        return

    async for chunk in stream_ollama_chat(model=model_name, messages=messages):
        yield chunk


async def complete_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
) -> str:
    chunks: list[str] = []
    async for chunk in stream_chat(model=model, messages=messages):
        delta = chunk.get("message", {}).get("content", "")
        if delta:
            chunks.append(delta)
    return "".join(chunks).strip()
