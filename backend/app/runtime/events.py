from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CanonicalEventKind = Literal[
    "meta",
    "status",
    "reasoning_delta",
    "output_text_delta",
    "sources",
    "context",
    "completed",
    "failed",
]


@dataclass(frozen=True)
class CanonicalEvent:
    kind: CanonicalEventKind
    payload: dict[str, Any] = field(default_factory=dict)


def meta_event(**payload: Any) -> CanonicalEvent:
    return CanonicalEvent(kind="meta", payload=payload)


def status_event(items: list[str]) -> CanonicalEvent:
    return CanonicalEvent(kind="status", payload={"items": items})


def reasoning_delta_event(content: str) -> CanonicalEvent:
    return CanonicalEvent(kind="reasoning_delta", payload={"content": content})


def output_text_delta_event(content: str) -> CanonicalEvent:
    return CanonicalEvent(kind="output_text_delta", payload={"content": content})


def sources_event(sources: list[dict[str, object]]) -> CanonicalEvent:
    return CanonicalEvent(kind="sources", payload={"sources": sources})


def context_event(context: dict[str, object]) -> CanonicalEvent:
    return CanonicalEvent(kind="context", payload={"context": context})


def completed_event(**payload: Any) -> CanonicalEvent:
    return CanonicalEvent(kind="completed", payload=payload)


def failed_event(message: str) -> CanonicalEvent:
    return CanonicalEvent(kind="failed", payload={"message": message})
