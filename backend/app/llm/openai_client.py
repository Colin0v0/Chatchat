from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from ..chat.types import ChatMessagePayload
from ..core.config import settings
from .capabilities import (
    DiscoveredModel,
    Provider,
    filter_chat_model_names,
    namespaced_model,
    normalize_base_url,
    parse_openai_allowlist,
    parse_openai_vision_allowlist,
)


def openai_base_url(provider: Provider = "openai", base_url_override: str | None = None) -> str:
    if base_url_override:
        return base_url_override
    if provider == "openai_local":
        return settings.openai_local_base_url
    return settings.openai_base_url


def openai_headers(provider: Provider = "openai", api_key_override: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    api_key = api_key_override or (
        settings.openai_local_api_key if provider == "openai_local" else settings.openai_api_key
    )
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def _list_openai_models_for_provider(provider: Provider) -> list[DiscoveredModel]:
    allowlist = parse_openai_allowlist(provider)
    vision_models = parse_openai_vision_allowlist(provider)
    try:
        async with httpx.AsyncClient(
            base_url=normalize_base_url(openai_base_url(provider)),
            timeout=10.0,
            headers=openai_headers(provider),
        ) as client:
            response = await client.get("/models")
            response.raise_for_status()
    except httpx.HTTPError:
        return [
            DiscoveredModel(
                id=namespaced_model(provider, model),
                supports_image_input=model in vision_models,
                supports_thinking=provider == "openai_local",
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
            id=namespaced_model(provider, model),
            supports_image_input=model in vision_models,
            supports_thinking=provider == "openai_local",
        )
        for model in models
    ]


async def list_openai_models() -> list[DiscoveredModel]:
    return await _list_openai_models_for_provider("openai")


async def list_openai_local_models() -> list[DiscoveredModel]:
    return await _list_openai_models_for_provider("openai_local")


def openai_message_payload(message: ChatMessagePayload) -> dict[str, object]:
    # 纯文本消息
    if not message.images and not message.documents:
        return {
            "role": message.role,
            "content": message.content,
        }

    # 多模态消息（图片+文档）
    content: list[dict[str, object]] = [{"type": "text", "text": message.content}]
    
    # 添加图片
    content.extend(
        {
            "type": "image_url",
            "image_url": {"url": image.data_url},
        }
        for image in message.images
    )
    
    # 添加PDF文档（Claude 3.5+ API格式）
    content.extend(
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": doc.mime_type,
                "data": doc.base64_data,
            },
        }
        for doc in message.documents
    )
    
    return {
        "role": message.role,
        "content": content,
    }


def _flush_sse_data_lines(data_lines: list[str]) -> str | None:
    if not data_lines:
        return None
    payload = "\n".join(data_lines).strip()
    data_lines.clear()
    return payload or None


async def _iter_openai_stream_payloads(lines: AsyncIterator[str]) -> AsyncIterator[str]:
    data_lines: list[str] = []
    in_sse_event = False

    async for raw_line in lines:
        line = raw_line.rstrip("\r")
        if not line:
            if not in_sse_event:
                continue
            payload = _flush_sse_data_lines(data_lines)
            in_sse_event = False
            if payload:
                yield payload
            continue

        if line.startswith(":"):
            in_sse_event = True
            continue

        field, separator, value = line.partition(":")
        if separator and field in {"data", "event", "id", "retry"}:
            in_sse_event = True
            if field == "data":
                data_lines.append(value[1:] if value.startswith(" ") else value)
            continue

        if in_sse_event:
            continue

        payload = line.strip()
        if payload:
            yield payload

    if in_sse_event:
        payload = _flush_sse_data_lines(data_lines)
        if payload:
            yield payload


def _decode_openai_stream_payload(payload: str) -> dict[str, object]:
    normalized = payload.strip()
    if not normalized:
        return {}
    if normalized == "[DONE]":
        return {"done": True}
    if normalized[0] not in "{[":
        return {}

    try:
        chunk = json.loads(normalized)
    except json.JSONDecodeError as exc:
        snippet = normalized[:160]
        raise RuntimeError(f"Model service returned malformed streaming event: {snippet}") from exc

    choices = chunk.get("choices") or []
    if not choices:
        return {}

    choice = choices[0]
    delta = choice.get("delta", {}).get("content", "")
    reasoning_delta = choice.get("delta", {}).get("reasoning_content", "")
    if not delta:
        delta = choice.get("message", {}).get("content", "")
    if not delta:
        delta = choice.get("text", "")

    event: dict[str, object] = {
        "done": choice.get("finish_reason") is not None,
    }
    if delta:
        event["message"] = {"content": delta}
    if reasoning_delta:
        event["reasoning"] = {"content": reasoning_delta}
    return event


async def stream_openai_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    provider: Provider = "openai",
    thinking_enabled: bool | None = None,
    base_url_override: str | None = None,
    api_key_override: str | None = None,
) -> AsyncIterator[dict]:
    use_stream = not (provider == "openai_local" and not settings.openai_local_stream)
    request_timeout = settings.request_timeout_seconds
    payload = {
        "model": model,
        "messages": [openai_message_payload(message) for message in messages],
        "stream": use_stream,
    }
    if provider == "openai_local" and thinking_enabled is not None:
        payload["thinking"] = {"type": "enabled" if thinking_enabled else "disabled"}

    async def _yield_non_stream_fallback() -> AsyncIterator[dict]:
        fallback_payload = dict(payload)
        fallback_payload["stream"] = False
        async with httpx.AsyncClient(
            base_url=normalize_base_url(openai_base_url(provider, base_url_override)),
            timeout=httpx.Timeout(request_timeout, connect=10.0),
            headers=openai_headers(provider, api_key_override),
        ) as fallback_client:
            fallback_response = await fallback_client.post("/chat/completions", json=fallback_payload)
            fallback_response.raise_for_status()
            payload_data = fallback_response.json()
            choices = payload_data.get("choices") or []
            if not choices:
                return
            message_payload = choices[0].get("message", {})
            content = message_payload.get("content", "")
            reasoning_text = message_payload.get("reasoning_content", "")
            if reasoning_text:
                yield {"reasoning": {"content": reasoning_text}}
            if content:
                yield {"message": {"content": content}}
            yield {"done": True}

    if not use_stream:
        async for event in _yield_non_stream_fallback():
            yield event
        return

    stream_timeout = httpx.Timeout(
        connect=10.0,
        read=None,
        write=request_timeout,
        pool=request_timeout,
    )
    async with httpx.AsyncClient(
        base_url=normalize_base_url(openai_base_url(provider, base_url_override)),
        timeout=stream_timeout,
        headers=openai_headers(provider, api_key_override),
    ) as client:
        emitted_any = False
        try:
            async with client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for payload_text in _iter_openai_stream_payloads(response.aiter_lines()):
                    chunk = _decode_openai_stream_payload(payload_text)
                    if not chunk:
                        continue
                    if chunk.get("done") and "message" not in chunk and "reasoning" not in chunk:
                        yield {"done": True}
                        return

                    delta = ""
                    if "message" in chunk:
                        delta = chunk["message"].get("content", "")
                    reasoning_delta = ""
                    if "reasoning" in chunk:
                        reasoning_delta = chunk["reasoning"].get("content", "")

                    event: dict[str, object] = {}
                    if delta:
                        event["message"] = {"content": delta}
                    if reasoning_delta:
                        event["reasoning"] = {"content": reasoning_delta}
                    if chunk.get("done"):
                        event["done"] = True

                    if event:
                        emitted_any = True
                        yield event
                if emitted_any:
                    yield {"done": True}
        except httpx.TransportError:
            # Some OpenAI-compatible routers intermittently close chunked streams early.
            if emitted_any:
                yield {"done": True}
                return
            async for event in _yield_non_stream_fallback():
                yield event
