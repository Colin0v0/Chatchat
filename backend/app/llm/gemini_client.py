from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from ..chat.types import ChatDocumentPayload, ChatImagePayload, ChatMessagePayload
from ..core.config import settings
from ..core.http import limited_request, shared_http_clients
from .capabilities import (
    DiscoveredModel,
    filter_chat_model_names,
    namespaced_model,
    normalize_base_url,
    parse_gemini_allowlist,
)
from .sse import iter_sse_payloads

logger = logging.getLogger("chatchat.llm.gemini")


def _gemini_http_limits() -> httpx.Limits:
    return httpx.Limits(
        max_connections=max(1, settings.http_pool_max_connections),
        max_keepalive_connections=max(1, settings.http_pool_max_keepalive_connections),
    )


def _gemini_request_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        settings.request_timeout_seconds,
        connect=settings.openai_connect_timeout_seconds,
    )


def _gemini_stream_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=settings.openai_connect_timeout_seconds,
        read=settings.request_timeout_seconds,
        write=settings.request_timeout_seconds,
        pool=settings.request_timeout_seconds,
    )


def gemini_base_url(base_url_override: str | None = None) -> str:
    return base_url_override or settings.gemini_base_url


def gemini_headers(api_key_override: str | None = None) -> dict[str, str]:
    api_key = api_key_override or settings.gemini_api_key
    if not api_key:
        return {}
    return {"x-goog-api-key": api_key}


async def _gemini_client(
    *,
    base_url_override: str | None,
    api_key_override: str | None,
    timeout: httpx.Timeout,
) -> httpx.AsyncClient:
    return await shared_http_clients.get_client(
        base_url=normalize_base_url(gemini_base_url(base_url_override)),
        headers=gemini_headers(api_key_override),
        timeout=timeout,
        limits=_gemini_http_limits(),
    )


def _normalize_model_name(name: str) -> str:
    normalized = name.strip()
    if "/" in normalized:
        normalized = normalized.rsplit("/", 1)[-1]
    return normalized


async def list_gemini_models() -> list[DiscoveredModel]:
    allowlist = parse_gemini_allowlist()
    try:
        async with limited_request(gate="gemini", max_concurrency=max(1, settings.openai_http_max_concurrency)):
            client = await _gemini_client(
                base_url_override=None,
                api_key_override=None,
                timeout=_gemini_request_timeout(),
            )
            response = await client.get("/v1beta/models")
            response.raise_for_status()
    except httpx.HTTPError:
        return [
            DiscoveredModel(
                id=namespaced_model("gemini", model),
                supports_thinking=False,
                native_multimodal="gemini",
            )
            for model in filter_chat_model_names(allowlist)
        ]

    payload = response.json()
    models = [
        _normalize_model_name(str(item.get("name", "")))
        for item in payload.get("models", [])
        if str(item.get("name", "")).strip()
    ]
    if allowlist:
        allowed = set(allowlist)
        models = [model for model in models if model in allowed]
    models = filter_chat_model_names(models)
    return [
        DiscoveredModel(
            id=namespaced_model("gemini", model),
            supports_thinking=False,
            native_multimodal="gemini",
        )
        for model in models
    ]


def _image_part(image: ChatImagePayload) -> dict[str, object]:
    _, _, encoded = image.data_url.partition(",")
    if not encoded:
        raise RuntimeError("Gemini image input is missing base64 data.")
    return {
        "inlineData": {
            "mimeType": image.mime_type,
            "data": encoded,
        }
    }


def _gemini_parts(message: ChatMessagePayload) -> list[dict[str, object]]:
    parts: list[dict[str, object]] = []
    if message.content:
        parts.append({"text": message.content})
    parts.extend(_image_part(image) for image in message.images)
    parts.extend(
        {
            "inlineData": {
                "mimeType": document.mime_type,
                "data": document.base64_data,
            }
        }
        for document in message.documents
    )

    if message.files:
        raise RuntimeError("Gemini provider does not support file-id references in the current route.")
    return parts


def gemini_request_payload(messages: list[ChatMessagePayload]) -> dict[str, object]:
    system_parts: list[dict[str, object]] = []
    contents: list[dict[str, object]] = []

    for message in messages:
        if message.role == "system":
            system_parts.extend(_gemini_parts(message))
            continue

        role = "model" if message.role == "assistant" else "user"
        parts = _gemini_parts(message)
        if not parts:
            continue
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].extend(parts)
            continue
        contents.append({"role": role, "parts": parts})

    payload: dict[str, object] = {"contents": contents}
    if system_parts:
        payload["systemInstruction"] = {"parts": system_parts}
    return payload


def _decode_gemini_stream_payload(payload: str) -> dict[str, object]:
    if not payload or payload == "[DONE]":
        return {}
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to decode Gemini stream payload: {exc}") from exc
    if not isinstance(chunk, dict):
        return {}

    candidates = chunk.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return {}

    candidate = candidates[0] if isinstance(candidates[0], dict) else {}
    content = candidate.get("content", {})
    parts = content.get("parts", []) if isinstance(content, dict) else []
    message_chunks: list[str] = []
    reasoning_chunks: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = str(part.get("text", ""))
        if not text:
            continue
        if part.get("thought") is True:
            reasoning_chunks.append(text)
        else:
            message_chunks.append(text)

    event: dict[str, object] = {}
    if message_chunks:
        event["message"] = {"content": "".join(message_chunks)}
    if reasoning_chunks:
        event["reasoning"] = {"content": "".join(reasoning_chunks)}
    if candidate.get("finishReason"):
        event["done"] = True
    return event


def _extract_gemini_output(payload: dict[str, object]) -> dict[str, str]:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return {"message": "", "reasoning": ""}

    candidate = candidates[0] if isinstance(candidates[0], dict) else {}
    content = candidate.get("content", {})
    parts = content.get("parts", []) if isinstance(content, dict) else []
    message_chunks: list[str] = []
    reasoning_chunks: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = str(part.get("text", ""))
        if not text:
            continue
        if part.get("thought") is True:
            reasoning_chunks.append(text)
        else:
            message_chunks.append(text)
    return {"message": "".join(message_chunks), "reasoning": "".join(reasoning_chunks)}


async def stream_gemini_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    base_url_override: str | None = None,
    api_key_override: str | None = None,
) -> AsyncIterator[dict]:
    payload = gemini_request_payload(messages)
    image_count = sum(len(message.images) for message in messages)
    document_count = sum(len(message.documents) for message in messages)
    logger.info("stream_gemini_chat called | model=%s", model)
    logger.info(
        "stream_gemini_chat target | base_url=%s | message_count=%s | image_count=%s | document_count=%s",
        normalize_base_url(gemini_base_url(base_url_override)),
        len(messages),
        image_count,
        document_count,
    )

    async with limited_request(gate="gemini", max_concurrency=max(1, settings.openai_http_max_concurrency)):
        client = await _gemini_client(
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            timeout=_gemini_stream_timeout(),
        )

        async with client.stream(
            "POST",
            f"/v1beta/models/{model}:streamGenerateContent?alt=sse",
            json=payload,
        ) as response:
            logger.info(
                "stream_gemini_chat response | model=%s | status=%s",
                model,
                response.status_code,
            )
            response.raise_for_status()
            async for raw_payload in iter_sse_payloads(response.aiter_lines()):
                chunk = _decode_gemini_stream_payload(raw_payload)
                if not chunk:
                    continue
                if chunk.get("done") and "message" not in chunk and "reasoning" not in chunk:
                    yield {"done": True}
                    continue
                event: dict[str, object] = {}
                message_delta = chunk.get("message", {}).get("content", "")
                if message_delta:
                    event["message"] = {"content": message_delta}
                reasoning_delta = chunk.get("reasoning", {}).get("content", "")
                if reasoning_delta:
                    event["reasoning"] = {"content": reasoning_delta}
                if chunk.get("done"):
                    event["done"] = True
                if event:
                    yield event
