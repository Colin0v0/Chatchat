from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

from ..chat.types import ChatMessagePayload
from ..core.config import settings
from ..core.http import limited_request, shared_http_clients
from ..provider_codecs.anthropic import (
    _decode_claude_stream_payload,
    _extract_claude_output,
    claude_request_payload,
)
from ..llm.capabilities import (
    DiscoveredModel,
    filter_chat_model_names,
    namespaced_model,
    normalize_base_url,
    parse_openai_allowlist,
)
from ..llm.sse import iter_sse_payloads

logger = logging.getLogger("chatchat.transport.claude")

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
    reasoning_profile: str | None = None,
    base_url_override: str | None = None,
    api_key_override: str | None = None,
) -> AsyncIterator[dict]:
    payload = claude_request_payload(
        messages,
        max_tokens=CLAUDE_DEFAULT_MAX_TOKENS,
        stream=True,
        reasoning_profile=reasoning_profile,
    )
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
    reasoning_profile: str | None = None,
    base_url_override: str | None = None,
    api_key_override: str | None = None,
) -> AsyncIterator[dict]:
    payload = claude_request_payload(
        messages,
        max_tokens=CLAUDE_DEFAULT_MAX_TOKENS,
        stream=False,
        reasoning_profile=reasoning_profile,
    )
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
