from __future__ import annotations

import base64
import io

from PIL import Image

from ..chat.types import ChatImagePayload, ChatMessagePayload


def ollama_image_base64(image: ChatImagePayload) -> str:
    encoded = image.data_url.split(",", 1)[1]
    if image.mime_type == "image/jpeg":
        return encoded

    raw = base64.b64decode(encoded)
    with Image.open(io.BytesIO(raw)) as decoded:
        frame = decoded.convert("RGB")
        buffer = io.BytesIO()
        frame.save(buffer, format="JPEG", quality=92)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def ollama_message_payload(message: ChatMessagePayload) -> dict[str, object]:
    payload: dict[str, object] = {
        "role": message.role,
        "content": message.content,
    }
    if message.images:
        payload["images"] = [ollama_image_base64(image) for image in message.images]
    return payload


def ollama_think_setting(reasoning_profile: str | None) -> bool:
    normalized = (reasoning_profile or "").strip().lower()
    if normalized == "off":
        return False
    return True
