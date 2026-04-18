from __future__ import annotations

import json

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

