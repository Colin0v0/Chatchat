from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

import httpx

from ..chat.types import ChatDocumentPayload, ChatImagePayload, ChatMessagePayload
from ..core.config import settings
from ..core.http import limited_request, shared_http_clients
from .capabilities import DiscoveredModel, filter_chat_model_names, namespaced_model, normalize_base_url, parse_openai_allowlist
from .sse import iter_sse_payloads

logger = logging.getLogger("chatchat.llm.claude")

CLAUDE_API_VERSION = "2023-06-01"
CLAUDE_DEFAULT_MAX_TOKENS = 4096


def _claude_http_limits() -> httpx.Limits:
    return httpx.Limits(
        max_connections=max(1, settings.http_pool_max_connections),
        max_keepalive_connections=max(1, settings.http_pool_max_keepalive_connections),
    )


def _claude_request_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        settings.request_timeout_seconds,
        connect=settings.openai_connect_timeout_seconds,
    )


def _claude_stream_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=settings.openai_connect_timeout_seconds,
        read=None,
        write=settings.request_timeout_seconds,
        pool=settings.request_timeout_seconds,
    )


def claude_base_url(base_url_override: str | None = None) -> str:
    return base_url_override or settings.claude_base_url


def claude_headers(api_key_override: str | None = None) -> dict[str, str]:
    api_key = (api_key_override or settings.claude_api_key).strip()
    if not api_key:
        return {}
    return {
        "x-api-key": api_key,
        "anthropic-version": CLAUDE_API_VERSION,
    }


async def _claude_client(*, base_url_override: str | None, api_key_override: str | None, timeout: httpx.Timeout) -> httpx.AsyncClient:
    return await shared_http_clients.get_client(
        base_url=normalize_base_url(claude_base_url(base_url_override)),
        headers=claude_headers(api_key_override),
        timeout=timeout,
        limits=_claude_http_limits(),
    )


def _claude_image_part(image: ChatImagePayload) -> dict[str, object]:
    _, _, encoded = image.data_url.partition(",")
    if not encoded:
        raise RuntimeError("Claude image input is missing base64 data.")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": image.mime_type,
            "data": encoded,
        },
    }


def _claude_document_part(document: ChatDocumentPayload) -> dict[str, object]:
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": document.mime_type,
            "data": document.base64_data,
        },
    }


def _claude_content_blocks(message: ChatMessagePayload) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    if message.content:
        blocks.append({"type": "text", "text": message.content})
    blocks.extend(_claude_image_part(image) for image in message.images)
    blocks.extend(_claude_document_part(document) for document in message.documents)
    if message.files:
        raise RuntimeError("Claude provider does not support file-id references in the current route.")
    return blocks


def claude_request_payload(messages: list[ChatMessagePayload], *, max_tokens: int, stream: bool) -> dict[str, object]:
    system_parts: list[str] = []
    chat_messages: list[dict[str, object]] = []

    for message in messages:
        if message.role == "system":
            if message.content.strip():
                system_parts.append(message.content.strip())
            continue

        role = "assistant" if message.role == "assistant" else "user"
        content = _claude_content_blocks(message)
        if not content:
            continue
        if chat_messages and chat_messages[-1]["role"] == role:
            chat_messages[-1]["content"].extend(content)
            continue
        chat_messages.append({"role": role, "content": content})

    payload: dict[str, object] = {
        "model": "",
        "messages": chat_messages,
        "max_tokens": max_tokens,
        "stream": stream,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)
    return payload


def _extract_claude_output(payload: dict[str, object]) -> dict[str, str]:
    blocks = payload.get("content")
    if not isinstance(blocks, list):
        return {"message": "", "reasoning": ""}

    message_chunks: list[str] = []
    reasoning_chunks: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type", "")).strip()
        if block_type == "text":
            text = str(block.get("text", "") or "")
            if text:
                message_chunks.append(text)
        elif block_type == "thinking":
            thinking = str(block.get("thinking", "") or "")
            if thinking:
                reasoning_chunks.append(thinking)

    return {
        "message": "".join(message_chunks),
        "reasoning": "".join(reasoning_chunks),
    }


def _decode_claude_stream_payload(payload: str) -> dict[str, object]:
    if not payload:
        return {}
    try:
        chunk = json.loads(payload)
    except json.JSONDecodeError as exc:
        snippet = payload[:160]
        raise RuntimeError(f"Claude service returned malformed streaming event: {snippet}") from exc

    if not isinstance(chunk, dict):
        return {}

    event_type = str(chunk.get("type", "")).strip()
    if not event_type:
        return {}

    if event_type == "content_block_delta":
        delta = chunk.get("delta", {})
        if not isinstance(delta, dict):
            return {}
        delta_type = str(delta.get("type", "")).strip()
        if delta_type == "text_delta":
            text = str(delta.get("text", "") or "")
            return {"message": {"content": text}} if text else {}
        if delta_type == "thinking_delta":
            thinking = str(delta.get("thinking", "") or "")
            return {"reasoning": {"content": thinking}} if thinking else {}
        return {}

    if event_type == "message_stop":
        return {"done": True}

    if event_type == "error":
        error = chunk.get("error", {})
        if isinstance(error, dict):
            message = str(error.get("message", "")).strip()
        else:
            message = ""
        raise RuntimeError(message or "Claude service returned a streaming error event.")

    return {}


async def list_claude_models() -> list[DiscoveredModel]:
    allowlist = parse_openai_allowlist("claude")
    try:
        async with limited_request(gate="claude", max_concurrency=max(1, settings.claude_http_max_concurrency)):
            client = await _claude_client(
                base_url_override=None,
                api_key_override=None,
                timeout=_claude_request_timeout(),
            )
            response = await client.get("/v1/models")
            response.raise_for_status()
    except httpx.HTTPError:
        return [
            DiscoveredModel(
                id=namespaced_model("claude", model),
                supports_thinking=False,
                native_multimodal="claude",
            )
            for model in filter_chat_model_names(allowlist)
        ]

    payload = response.json()
    items = payload.get("data") if isinstance(payload, dict) else []
    models = [str(item.get("id", "")).strip() for item in items if isinstance(item, dict) and item.get("id")]
    if allowlist:
        allowed = set(allowlist)
        models = [model for model in models if model in allowed]
    models = filter_chat_model_names(models)
    return [
        DiscoveredModel(
            id=namespaced_model("claude", model),
            supports_thinking=False,
            native_multimodal="claude",
        )
        for model in models
    ]


async def stream_claude_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    base_url_override: str | None = None,
    api_key_override: str | None = None,
) -> AsyncIterator[dict]:
    payload = claude_request_payload(messages, max_tokens=CLAUDE_DEFAULT_MAX_TOKENS, stream=True)
    payload["model"] = model

    client = await _claude_client(
        base_url_override=base_url_override,
        api_key_override=api_key_override,
        timeout=_claude_stream_timeout(),
    )
    emitted_any = False
    try:
        async with limited_request(gate="claude", max_concurrency=max(1, settings.claude_http_max_concurrency)):
            async with client.stream("POST", "/v1/messages", json=payload) as response:
                response.raise_for_status()
                async for payload_text in iter_sse_payloads(response.aiter_lines()):
                    event = _decode_claude_stream_payload(payload_text)
                    if not event:
                        continue
                    emitted_any = True
                    yield event
    except httpx.TransportError:
        if emitted_any:
            yield {"done": True}
            return
        raise


async def complete_claude_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    base_url_override: str | None = None,
    api_key_override: str | None = None,
) -> AsyncIterator[dict]:
    payload = claude_request_payload(messages, max_tokens=CLAUDE_DEFAULT_MAX_TOKENS, stream=False)
    payload["model"] = model

    async with limited_request(gate="claude", max_concurrency=max(1, settings.claude_http_max_concurrency)):
        client = await _claude_client(
            base_url_override=base_url_override,
            api_key_override=api_key_override,
            timeout=_claude_request_timeout(),
        )
        response = await client.post("/v1/messages", json=payload)
        response.raise_for_status()

    payload_data = response.json()
    output = _extract_claude_output(payload_data if isinstance(payload_data, dict) else {})
    if output["reasoning"]:
        yield {"reasoning": {"content": output["reasoning"]}}
    if output["message"]:
        yield {"message": {"content": output["message"]}}
    yield {"done": True}
