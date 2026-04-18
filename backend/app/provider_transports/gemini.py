from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

from ..chat.types import ChatMessagePayload
from ..core.config import settings
from ..core.http import limited_request, shared_http_clients
from ..provider_codecs.gemini import (
    _decode_gemini_stream_payload,
    _extract_gemini_output,
    gemini_request_payload,
)
from ..llm.capabilities import (
    DiscoveredModel,
    filter_chat_model_names,
    namespaced_model,
    normalize_base_url,
    parse_gemini_allowlist,
)
from ..llm.sse import iter_sse_payloads

logger = logging.getLogger("chatchat.transport.gemini")


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
