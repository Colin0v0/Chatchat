from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChatImagePayload:
    mime_type: str
    data_url: str


@dataclass(frozen=True)
class ChatMessagePayload:
    role: str
    content: str
    images: tuple[ChatImagePayload, ...] = field(default_factory=tuple)
