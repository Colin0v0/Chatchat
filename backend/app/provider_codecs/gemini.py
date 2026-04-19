from __future__ import annotations

import json
from typing import cast

from ..chat.types import ChatDocumentPayload, ChatImagePayload, ChatMessagePayload


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


def _normalize_reasoning_profile(reasoning_profile: str | None) -> str:
    return (reasoning_profile or "").strip().lower()


def _gemini_thinking_budget(reasoning_profile: str | None) -> int | None:
    normalized = _normalize_reasoning_profile(reasoning_profile)
    if normalized in {"", "auto", "provider_default"}:
        return 1024
    if normalized == "off":
        return 0
    if normalized == "low":
        return 512
    if normalized == "medium":
        return 1024
    if normalized == "high":
        return 2048
    if normalized == "max":
        return 4096
    return 1024


def apply_gemini_reasoning_controls(payload: dict[str, object], *, reasoning_profile: str | None) -> None:
    budget = _gemini_thinking_budget(reasoning_profile)
    if budget is None:
        return
    generation_config = cast(dict[str, object], payload.setdefault("generationConfig", {}))
    generation_config["thinkingConfig"] = {
        "includeThoughts": budget > 0,
        "thinkingBudget": budget,
    }


def gemini_request_payload(messages: list[ChatMessagePayload], *, reasoning_profile: str | None = None) -> dict[str, object]:
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
    apply_gemini_reasoning_controls(payload, reasoning_profile=reasoning_profile)
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
