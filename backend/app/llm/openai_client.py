from __future__ import annotations

import json
import re
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


def _strip_think_blocks(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()


def _extract_think_blocks(text: str) -> tuple[str, str]:
    pattern = re.compile(r"<think>(.*?)</think>", flags=re.IGNORECASE | re.DOTALL)
    reasoning_parts = [match.group(1).strip() for match in pattern.finditer(text) if match.group(1).strip()]
    answer = pattern.sub("", text).strip()
    return "\n\n".join(reasoning_parts), answer


class _ThinkTagStripper:
    def __init__(self) -> None:
        self._in_think = False
        self._carry = ""
        self._open_tag = "<think>"
        self._close_tag = "</think>"

    def _suffix_len_matching_prefix(self, text: str, prefix: str) -> int:
        max_len = min(len(text), len(prefix) - 1)
        for size in range(max_len, 0, -1):
            if text.endswith(prefix[:size]):
                return size
        return 0

    def feed(self, chunk: str) -> str:
        data = self._carry + chunk
        self._carry = ""
        out: list[str] = []
        i = 0

        while i < len(data):
            if self._in_think:
                close_at = data.find(self._close_tag, i)
                if close_at == -1:
                    tail = data[i:]
                    keep = self._suffix_len_matching_prefix(tail, self._close_tag)
                    self._carry = tail[-keep:] if keep else ""
                    return "".join(out)
                i = close_at + len(self._close_tag)
                self._in_think = False
                continue

            open_at = data.find(self._open_tag, i)
            if open_at == -1:
                remain = data[i:]
                keep = self._suffix_len_matching_prefix(remain, self._open_tag)
                if keep:
                    out.append(remain[:-keep])
                    self._carry = remain[-keep:]
                else:
                    out.append(remain)
                return "".join(out)

            out.append(data[i:open_at])
            i = open_at + len(self._open_tag)
            self._in_think = True

        return "".join(out)


class _ThinkTagSplitter:
    def __init__(self) -> None:
        self._in_think = False
        self._carry = ""
        self._open_tag = "<think>"
        self._close_tag = "</think>"

    def _suffix_len_matching_prefix(self, text: str, prefix: str) -> int:
        max_len = min(len(text), len(prefix) - 1)
        for size in range(max_len, 0, -1):
            if text.endswith(prefix[:size]):
                return size
        return 0

    def feed(self, chunk: str) -> tuple[str, str]:
        data = self._carry + chunk
        self._carry = ""
        reasoning: list[str] = []
        answer: list[str] = []
        i = 0

        while i < len(data):
            if self._in_think:
                close_at = data.find(self._close_tag, i)
                if close_at == -1:
                    tail = data[i:]
                    keep = self._suffix_len_matching_prefix(tail, self._close_tag)
                    if keep:
                        reasoning.append(tail[:-keep])
                        self._carry = tail[-keep:]
                    else:
                        reasoning.append(tail)
                    return "".join(reasoning), "".join(answer)
                reasoning.append(data[i:close_at])
                i = close_at + len(self._close_tag)
                self._in_think = False
                continue

            open_at = data.find(self._open_tag, i)
            if open_at == -1:
                tail = data[i:]
                keep = self._suffix_len_matching_prefix(tail, self._open_tag)
                if keep:
                    answer.append(tail[:-keep])
                    self._carry = tail[-keep:]
                else:
                    answer.append(tail)
                return "".join(reasoning), "".join(answer)

            answer.append(data[i:open_at])
            i = open_at + len(self._open_tag)
            self._in_think = True

        return "".join(reasoning), "".join(answer)

    def flush(self) -> tuple[str, str]:
        if not self._carry:
            return "", ""
        if self._in_think:
            tail = self._carry
            self._carry = ""
            return tail, ""
        tail = self._carry
        self._carry = ""
        return "", tail


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
    payload = {
        "model": model,
        "messages": [openai_message_payload(message) for message in messages],
        "stream": use_stream,
    }
    if provider == "openai_local" and thinking_enabled is not None:
        payload["thinking"] = {"type": "enabled" if thinking_enabled else "disabled"}

    split_thinking = provider == "openai_local" and thinking_enabled is not False
    strip_thinking = provider == "openai_local" and thinking_enabled is False
    think_stripper = _ThinkTagStripper() if strip_thinking else None
    think_splitter = _ThinkTagSplitter() if split_thinking else None

    async def _yield_non_stream_fallback() -> AsyncIterator[dict]:
        fallback_payload = dict(payload)
        fallback_payload["stream"] = False
        async with httpx.AsyncClient(
            base_url=normalize_base_url(openai_base_url(provider, base_url_override)),
            timeout=timeout,
            headers=openai_headers(provider, api_key_override),
        ) as fallback_client:
            fallback_response = await fallback_client.post("/chat/completions", json=fallback_payload)
            fallback_response.raise_for_status()
            payload_data = fallback_response.json()
            choices = payload_data.get("choices") or []
            if not choices:
                return
            content = choices[0].get("message", {}).get("content", "")
            reasoning_text = ""
            if think_splitter and content:
                reasoning_text, content = _extract_think_blocks(content)
            if strip_thinking and content:
                content = _strip_think_blocks(content)
            if reasoning_text:
                yield {"reasoning": {"content": reasoning_text}}
            if content:
                yield {"message": {"content": content}}
            yield {"done": True}

    timeout = httpx.Timeout(settings.request_timeout_seconds, connect=10.0)
    if not use_stream:
        async for event in _yield_non_stream_fallback():
            yield event
        return

    async with httpx.AsyncClient(
        base_url=normalize_base_url(openai_base_url(provider, base_url_override)),
        timeout=timeout,
        headers=openai_headers(provider, api_key_override),
    ) as client:
        emitted_any = False
        try:
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
                    if not delta:
                        delta = choice.get("message", {}).get("content", "")
                    if not delta:
                        delta = choice.get("text", "")
                    if think_stripper and delta:
                        delta = think_stripper.feed(delta)
                    if think_splitter and delta:
                        split_reasoning, split_answer = think_splitter.feed(delta)
                        if split_reasoning:
                            reasoning_delta = f"{reasoning_delta}{split_reasoning}"
                        delta = split_answer
                    finish_reason = choice.get("finish_reason")

                    event: dict[str, object] = {}
                    if delta:
                        event["message"] = {"content": delta}
                    if reasoning_delta:
                        event["reasoning"] = {"content": reasoning_delta}
                    if finish_reason is not None:
                        event["done"] = True

                    if event:
                        emitted_any = True
                        yield event
                if think_splitter:
                    tail_reasoning, tail_answer = think_splitter.flush()
                    if tail_reasoning:
                        emitted_any = True
                        yield {"reasoning": {"content": tail_reasoning}}
                    if tail_answer:
                        emitted_any = True
                        yield {"message": {"content": tail_answer}}
                if emitted_any:
                    yield {"done": True}
        except httpx.TransportError:
            # Some OpenAI-compatible routers intermittently close chunked streams early.
            if emitted_any:
                yield {"done": True}
                return
            async for event in _yield_non_stream_fallback():
                yield event
