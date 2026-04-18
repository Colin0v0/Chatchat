from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

import httpx

from ..chat.types import ChatMessagePayload
from ..core.config import settings
from ..core.http import limited_request, shared_http_clients
from ..provider_codecs.ollama import ollama_message_payload, ollama_think_setting
from ..llm.ollama_runtime import log_ollama_request, ollama_keep_alive_value
from ..llm.capabilities import (
    DiscoveredModel,
    OLLAMA_CAPABILITY_CACHE,
    filter_chat_model_names,
    namespaced_model,
    normalize_base_url,
)


def _ollama_http_limits() -> httpx.Limits:
    return httpx.Limits(
        max_connections=max(1, settings.http_pool_max_connections),
        max_keepalive_connections=max(1, settings.http_pool_max_keepalive_connections),
    )


def _ollama_timeout() -> httpx.Timeout:
    return httpx.Timeout(settings.request_timeout_seconds, connect=10.0)


async def _ollama_client(*, base_url: str, timeout: httpx.Timeout) -> httpx.AsyncClient:
    return await shared_http_clients.get_client(
        base_url=normalize_base_url(base_url),
        timeout=timeout,
        limits=_ollama_http_limits(),
    )


async def fetch_ollama_capabilities(model_name: str) -> set[str]:
    async with limited_request(gate="ollama", max_concurrency=settings.ollama_http_max_concurrency):
        client = await _ollama_client(
            base_url=settings.ollama_base_url,
            timeout=httpx.Timeout(10.0),
        )
        response = await client.post("/api/show", json={"model": model_name})
        response.raise_for_status()
        payload = response.json()
    capabilities = payload.get("capabilities") or []
    return {str(item).strip().lower() for item in capabilities if str(item).strip()}


async def list_ollama_models() -> list[DiscoveredModel]:
    try:
        async with limited_request(gate="ollama", max_concurrency=settings.ollama_http_max_concurrency):
            client = await _ollama_client(
                base_url=settings.ollama_base_url,
                timeout=httpx.Timeout(10.0),
            )
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
                supports_thinking="thinking" in capabilities,
                native_multimodal="false",
            )
        )
    return discovered


def ollama_supports_thinking(model_name: str) -> bool:
    return "thinking" in OLLAMA_CAPABILITY_CACHE.get(model_name, set())


async def stream_ollama_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    reasoning_profile: str | None = None,
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
        payload["think"] = ollama_think_setting(reasoning_profile)
    if isinstance(context_window, int) and context_window > 0:
        payload["options"] = {"num_ctx": context_window}

    started_at = time.perf_counter()
    client = await _ollama_client(
        base_url=base_url_override or settings.ollama_base_url,
        timeout=_ollama_timeout(),
    )
    async with limited_request(gate="ollama", max_concurrency=settings.ollama_http_max_concurrency):
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
