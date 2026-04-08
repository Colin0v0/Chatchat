from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChatImagePayload:
    mime_type: str
    data_url: str


@dataclass(frozen=True)
class ChatDocumentPayload:
    """原生文档payload（用于Claude PDF支持）"""
    mime_type: str
    filename: str
    base64_data: str


@dataclass(frozen=True)
class ChatFileReferencePayload:
    file_id: str


@dataclass(frozen=True)
class ChatMessagePayload:
    role: str
    content: str
    images: tuple[ChatImagePayload, ...] = field(default_factory=tuple)
    documents: tuple[ChatDocumentPayload, ...] = field(default_factory=tuple)
    files: tuple[ChatFileReferencePayload, ...] = field(default_factory=tuple)
