from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from ..chat.types import ChatMessagePayload

MemoryScope = Literal["working", "conversation", "global"]
MemoryKind = Literal["profile", "preference", "goal", "project", "fact", "constraint"]
MemoryStatus = Literal["active", "archived"]
MemorySourceType = Literal["manual", "auto", "promoted"]
MemoryWritePolicy = Literal["manual", "explicit", "session"]
MemoryDocumentType = Literal["user_profile", "workspace_profile", "conversation_brief"]
MemoryAction = Literal["add", "update", "replace", "remove"]

MEMORY_SCOPES: tuple[MemoryScope, ...] = ("working", "conversation", "global")
MEMORY_KINDS: tuple[MemoryKind, ...] = (
    "profile",
    "preference",
    "goal",
    "project",
    "fact",
    "constraint",
)
MEMORY_STATUSES: tuple[MemoryStatus, ...] = ("active", "archived")
MEMORY_SOURCE_TYPES: tuple[MemorySourceType, ...] = ("manual", "auto", "promoted")
MEMORY_WRITE_POLICIES: tuple[MemoryWritePolicy, ...] = ("manual", "explicit", "session")
MEMORY_DOCUMENT_TYPES: tuple[MemoryDocumentType, ...] = (
    "user_profile",
    "workspace_profile",
    "conversation_brief",
)


@dataclass(frozen=True)
class MemoryCandidate:
    scope: MemoryScope
    kind: MemoryKind
    title: str
    detail: str = ""
    tags: tuple[str, ...] = ()
    confidence: float = 0.7
    action: MemoryAction = "add"


@dataclass(frozen=True)
class MemoryDocumentSnapshot:
    doc_type: MemoryDocumentType
    title: str
    content: str
    source_memory_ids: tuple[int, ...] = ()
    updated_at: datetime | None = None


@dataclass(frozen=True)
class MemoryPromptPayload:
    messages: tuple[ChatMessagePayload, ...] = ()
    debug: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryMatch:
    memory_id: int
    score: float


@dataclass(frozen=True)
class MemoryTurnPolicy:
    explicit_request: bool
    target_scope: MemoryScope | None
    allow_automatic_storage: bool
    skip_due_to_attachments: bool
    modality: str


@dataclass(frozen=True)
class MemoryWorkspaceCollection:
    documents: tuple[object, ...]
    active_global_items: tuple[object, ...]
    active_conversation_items: tuple[object, ...]
    active_working_items: tuple[object, ...]
