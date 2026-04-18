from __future__ import annotations

import json

import httpx

from ..chat.types import ChatMessagePayload
from ..llm.capabilities import Provider


def _normalize_reasoning_profile(reasoning_profile: str | None) -> str:
    return (reasoning_profile or "").strip().lower()


def _toggle_reasoning_state(reasoning_profile: str | None) -> str | None:
    normalized = _normalize_reasoning_profile(reasoning_profile)
    if normalized in {"", "auto", "provider_default"}:
        return None
    if normalized == "off":
        return "disabled"
    return "enabled"


def _reasoning_effort(reasoning_profile: str | None) -> str | None:
    normalized = _normalize_reasoning_profile(reasoning_profile)
    if normalized in {"", "auto", "provider_default"}:
        return None
    if normalized == "off":
        return "none"
    if normalized == "max":
        return "high"
    if normalized in {"low", "medium", "high"}:
        return normalized
    return "medium"


def apply_reasoning_controls(
    payload: dict[str, object],
    *,
    provider: Provider,
    reasoning_profile: str | None,
) -> None:
    if provider == "openai_local":
        toggle_state = _toggle_reasoning_state(reasoning_profile)
        if toggle_state is not None:
            payload["thinking"] = {"type": toggle_state}
        return
    if provider == "codex":
        effort = _reasoning_effort(reasoning_profile)
        if effort is not None:
            payload["reasoning_effort"] = effort


def apply_responses_reasoning_controls(payload: dict[str, object], *, reasoning_profile: str | None) -> None:
    effort = _reasoning_effort(reasoning_profile)
    if effort is None:
        return
    reasoning: dict[str, object] = {"effort": effort}
    if effort != "none":
        reasoning["summary"] = "auto"
    payload["reasoning"] = reasoning


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


def responses_message_payload(message: ChatMessagePayload) -> dict[str, object]:
    if not message.images and not message.documents and not message.files:
        return {
            "role": message.role,
            "content": message.content,
        }

    content: list[dict[str, object]] = []
    if message.content:
        content.append({"type": "input_text", "text": message.content})

    content.extend(
        {
            "type": "input_image",
            "image_url": image.data_url,
        }
        for image in message.images
    )

    content.extend(
        {
            "type": "input_file",
            "filename": doc.filename,
            "file_data": doc.base64_data,
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


def _decode_responses_stream_payload(payload: str) -> dict[str, object]:
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

    event_type = str(chunk.get("type", "")).strip()
    if not event_type:
        return {}
    if event_type == "response.output_text.delta":
        delta = str(chunk.get("delta", ""))
        return {"message": {"content": delta}} if delta else {}
    if event_type == "response.reasoning_summary_text.delta":
        delta = str(chunk.get("delta", ""))
        return {"reasoning": {"content": delta}} if delta else {}
    if event_type == "response.completed":
        return {"done": True}
    if event_type == "error":
        error = chunk.get("error")
        if isinstance(error, dict):
            message = str(error.get("message", "")).strip()
        else:
            message = str(chunk.get("message", "")).strip()
        raise RuntimeError(message or "Model service returned a streaming error event.")
    return {}


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


def _extract_responses_output(payload: dict[str, object]) -> dict[str, str]:
    output = payload.get("output")
    if not isinstance(output, list):
        return {"message": "", "reasoning": ""}

    message_chunks: list[str] = []
    reasoning_chunks: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "output_text":
                    continue
                text = str(part.get("text", ""))
                if text:
                    message_chunks.append(text)
        if item.get("type") == "reasoning":
            summary = item.get("summary")
            if not isinstance(summary, list):
                continue
            for part in summary:
                if not isinstance(part, dict):
                    continue
                text = str(part.get("text", ""))
                if text:
                    reasoning_chunks.append(text)
    return {"message": "".join(message_chunks), "reasoning": "".join(reasoning_chunks)}

