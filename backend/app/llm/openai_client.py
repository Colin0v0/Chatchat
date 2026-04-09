from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from ..chat.types import ChatMessagePayload
from ..core.config import settings
from ..core.http import limited_request, shared_http_clients
from .capabilities import (
    DiscoveredModel,
    Provider,
    filter_chat_model_names,
    namespaced_model,
    normalize_base_url,
    parse_openai_allowlist,
)


logger = logging.getLogger("chatchat.llm.openai")


def _openai_http_limits() -> httpx.Limits:
    return httpx.Limits(
        max_connections=max(1, settings.http_pool_max_connections),
        max_keepalive_connections=max(1, settings.http_pool_max_keepalive_connections),
    )


def _openai_request_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        settings.request_timeout_seconds,
        connect=settings.openai_connect_timeout_seconds,
    )


def _openai_stream_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=settings.openai_connect_timeout_seconds,
        read=None,
        write=settings.request_timeout_seconds,
        pool=settings.request_timeout_seconds,
    )


def _request_gate(provider: Provider) -> tuple[str, int]:
    if provider == "openai_local":
        return ("openai_local", max(1, settings.openai_local_http_max_concurrency))
    return ("openai", max(1, settings.openai_http_max_concurrency))


async def _openai_client(
    *,
    provider: Provider,
    base_url_override: str | None,
    api_key_override: str | None,
    timeout: httpx.Timeout,
) -> httpx.AsyncClient:
    return await shared_http_clients.get_client(
        base_url=normalize_base_url(openai_base_url(provider, base_url_override)),
        headers=openai_headers(provider, api_key_override),
        timeout=timeout,
        limits=_openai_http_limits(),
    )


async def _openai_upstream_client(
    *,
    provider: Provider,
    base_url_override: str | None,
    api_key_override: str | None,
) -> httpx.AsyncClient:
    return await shared_http_clients.get_client(
        base_url=normalize_base_url(openai_upstream_service_base_url(provider, base_url_override)),
        headers=openai_headers(provider, api_key_override),
        timeout=_openai_request_timeout(),
        limits=_openai_http_limits(),
    )


def openai_base_url(provider: Provider = "openai", base_url_override: str | None = None) -> str:
    if base_url_override:
        return base_url_override
    if provider == "openai_local":
        return settings.openai_local_base_url
    return settings.openai_base_url


def openai_upstream_service_base_url(
    provider: Provider = "openai",
    base_url_override: str | None = None,
) -> str:
    if base_url_override:
        return base_url_override
    if provider == "openai_local":
        return settings.openai_local_upstream_service_base_url or settings.openai_local_base_url
    return openai_base_url(provider)


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
    try:
        gate, max_concurrency = _request_gate(provider)
        async with limited_request(gate=gate, max_concurrency=max_concurrency):
            client = await _openai_client(
                provider=provider,
                base_url_override=None,
                api_key_override=None,
                timeout=_openai_request_timeout(),
            )
            response = await client.get("/models")
            response.raise_for_status()
    except httpx.HTTPError:
        return [
            DiscoveredModel(
                id=namespaced_model(provider, model),
                supports_thinking=provider == "openai_local",
                native_multimodal=False,
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
            supports_thinking=provider == "openai_local",
            native_multimodal=False,
        )
        for model in models
    ]


async def list_openai_models() -> list[DiscoveredModel]:
    return await _list_openai_models_for_provider("openai")


async def list_openai_local_models() -> list[DiscoveredModel]:
    return await _list_openai_models_for_provider("openai_local")


def openai_message_payload(message: ChatMessagePayload) -> dict[str, object]:
    if not message.images and not message.documents and not message.files:
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

    content.extend(
        {
            "type": "input_file",
            "file_id": file_ref.file_id,
        }
        for file_ref in message.files
    )

    return {
        "role": message.role,
        "content": content,
    }


async def upload_openai_file(
    *,
    filename: str,
    mime_type: str,
    file_path: Path,
    provider: Provider = "openai",
    base_url_override: str | None = None,
    api_key_override: str | None = None,
) -> str:
    content = file_path.read_bytes()
    if not content:
        raise RuntimeError(f"Cannot upload empty file to upstream service: {file_path.name}")

    gate, max_concurrency = _request_gate(provider)
    async with limited_request(gate=gate, max_concurrency=max_concurrency):
        client = await _openai_upstream_client(
            provider=provider,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
        )
        response = await client.post(
            "/files",
            data={"purpose": "user_data"},
            files={"file": (filename, content, mime_type)},
        )
        response.raise_for_status()

    payload = _parse_openai_json_response(response, context="files.upload")
    file_id = str(payload.get("id", "")).strip()
    if not file_id:
        raise RuntimeError("Upstream file upload succeeded but did not return a file id.")
    return file_id


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


def _parse_openai_json_response(response: httpx.Response, *, context: str) -> dict[str, object]:
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        text = response.text.strip()
        snippet = " ".join(text.split())[:220]
        if snippet:
            detail = f"Snippet: {snippet}"
        else:
            detail = "Response body was empty."
        raise RuntimeError(
            "Model service returned a non-JSON response. "
            f"Context: {context}. HTTP {response.status_code}. {detail}"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            "Model service returned an unexpected response shape. "
            f"Context: {context}. Expected JSON object."
        )
    return payload


async def stream_openai_chat(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    provider: Provider = "openai",
    thinking_enabled: bool | None = None,
    base_url_override: str | None = None,
    api_key_override: str | None = None,
) -> AsyncIterator[dict]:
    logger.info("stream_openai_chat called | model=%s | provider=%s | thinking_enabled=%s", model, provider, thinking_enabled)
    use_stream = not (provider == "openai_local" and not settings.openai_local_stream)
    payload = {
        "model": model,
        "messages": [openai_message_payload(message) for message in messages],
        "stream": use_stream,
    }
    if provider == "openai_local" and thinking_enabled is not None:
        logger.info("setting thinking in payload | type=%s", "enabled" if thinking_enabled else "disabled")
        payload["thinking"] = {"type": "enabled" if thinking_enabled else "disabled"}

    async def _yield_non_stream_completion() -> AsyncIterator[dict]:
        completion_payload = dict(payload)
        completion_payload["stream"] = False
        gate, max_concurrency = _request_gate(provider)
        async with limited_request(gate=gate, max_concurrency=max_concurrency):
            client = await _openai_client(
                provider=provider,
                base_url_override=base_url_override,
                api_key_override=api_key_override,
                timeout=_openai_request_timeout(),
            )
            response = await client.post("/chat/completions", json=completion_payload)
            response.raise_for_status()
        payload_data = _parse_openai_json_response(response, context="chat.completions")
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
        async for event in _yield_non_stream_completion():
            yield event
        return

    client = await _openai_client(
        provider=provider,
        base_url_override=base_url_override,
        api_key_override=api_key_override,
        timeout=_openai_stream_timeout(),
    )
    gate, max_concurrency = _request_gate(provider)
    emitted_any = False
    try:
        async with limited_request(gate=gate, max_concurrency=max_concurrency):
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
        raise
