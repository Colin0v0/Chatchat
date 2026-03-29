from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..chat.types import ChatMessagePayload

SourceType = Literal["note", "web"]


@dataclass(frozen=True)
class SourceItem:
    type: SourceType
    path: str = ""
    heading: str = ""
    excerpt: str = ""
    score: float | None = None
    title: str = ""
    url: str = ""
    domain: str = ""
    published_at: str = ""
    trust: str = ""
    freshness: str = ""
    match_reason: str = ""

    def to_payload(self) -> dict[str, str | float | None]:
        return {
            "type": self.type,
            "path": self.path,
            "heading": self.heading,
            "excerpt": self.excerpt,
            "score": None if self.score is None else round(self.score, 3),
            "title": self.title,
            "url": self.url,
            "domain": self.domain,
            "published_at": self.published_at,
            "trust": self.trust,
            "freshness": self.freshness,
            "match_reason": self.match_reason,
        }


@dataclass(frozen=True)
class ContextEntry:
    source: SourceItem
    content: str


@dataclass(frozen=True)
class ContextPayload:
    entries: list[ContextEntry] = field(default_factory=list)
    sources: list[SourceItem] = field(default_factory=list)
    should_refuse: bool = False
    refusal_message: str | None = None
    instructions: tuple[str, ...] = ()
    strategy_hint: str = "balanced"
    debug: dict[str, object] = field(default_factory=dict)

    @property
    def has_content(self) -> bool:
        return bool(self.entries)


@dataclass(frozen=True)
class PromptContextPayload:
    context_message: ChatMessagePayload | None
    sources: list[dict[str, str | float | None]] = field(default_factory=list)
    should_refuse: bool = False
    refusal_message: str | None = None
    debug: dict[str, object] = field(default_factory=dict)