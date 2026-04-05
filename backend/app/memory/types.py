from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..chat.types import ChatMessagePayload

MemoryScope = Literal["global", "conversation"]
MemoryKind = Literal["profile", "preference", "goal", "project", "fact", "constraint"]

MEMORY_SCOPES: tuple[MemoryScope, ...] = ("global", "conversation")
MEMORY_KINDS: tuple[MemoryKind, ...] = (
    "profile",
    "preference",
    "goal",
    "project",
    "fact",
    "constraint",
)


@dataclass(frozen=True)
class MemoryCandidate:
    scope: MemoryScope
    kind: MemoryKind
    title: str
    detail: str = ""
    tags: tuple[str, ...] = ()
    confidence: float = 0.7


@dataclass(frozen=True)
class MemoryMatch:
    memory_id: int
    score: float


@dataclass(frozen=True)
class MemoryPromptPayload:
    message: ChatMessagePayload | None
    memory_ids: tuple[int, ...] = ()
    debug: dict[str, object] = field(default_factory=dict)
