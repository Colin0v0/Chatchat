from __future__ import annotations

import json

from ..chat.types import ChatDocumentPayload, ChatImagePayload, ChatMessagePayload


def _normalize_reasoning_profile(reasoning_profile: str | None) -> str:
    return (reasoning_profile or "").strip().lower()


def _anthropic_budget_tokens(reasoning_profile: str | None) -> int | None:
    normalized = _normalize_reasoning_profile(reasoning_profile)
    if normalized in {"", "off"}:
        return None
    if normalized in {"auto", "provider_default"}:
        return 1536
    if normalized == "low":
        return 1024
    if normalized == "medium":
        return 1536
    if normalized == "high":
        return 2048
    if normalized == "max":
        return 3072
    return 1536


def apply_anthropic_reasoning_controls(payload: dict[str, object], *, reasoning_profile: str | None) -> None:
    budget_tokens = _anthropic_budget_tokens(reasoning_profile)
    if budget_tokens is None:
        return
    payload["thinking"] = {
        "type": "enabled",
        "budget_tokens": budget_tokens,
    }


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


def claude_request_payload(
    messages: list[ChatMessagePayload],
    *,
    max_tokens: int,
    stream: bool,
    reasoning_profile: str | None = None,
) -> dict[str, object]:
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
    apply_anthropic_reasoning_controls(payload, reasoning_profile=reasoning_profile)
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
