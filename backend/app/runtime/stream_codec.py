from __future__ import annotations

import json

from .events import CanonicalEvent


def encode_ndjson_event(event: CanonicalEvent) -> str | None:
    if event.kind == "meta":
        payload = {"type": "meta", **event.payload}
    elif event.kind == "status":
        payload = {"type": "status", "items": event.payload.get("items", [])}
    elif event.kind == "reasoning_delta":
        payload = {"type": "reasoning", "content": event.payload.get("content", "")}
    elif event.kind == "output_text_delta":
        payload = {"type": "token", "content": event.payload.get("content", "")}
    elif event.kind == "sources":
        payload = {"type": "sources", "sources": event.payload.get("sources", [])}
    elif event.kind == "context":
        payload = {"type": "context", "context": event.payload.get("context", {})}
    elif event.kind == "completed":
        payload = {"type": "done", **event.payload}
    elif event.kind == "failed":
        payload = {"type": "error", "message": event.payload.get("message", "")}
    else:
        return None
    return json.dumps(payload, ensure_ascii=False) + "\n"
