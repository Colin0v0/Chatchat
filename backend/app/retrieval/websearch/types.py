from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WebQuery:
    raw_query: str
    cleaned_query: str
    intent: str = "general"
    translated_query: str = ""
    include_domains: tuple[str, ...] = ()
    exclude_domains: tuple[str, ...] = ()
    preferred_domains: tuple[str, ...] = ()
    disfavored_domains: tuple[str, ...] = ()
    required_terms: tuple[str, ...] = ()
    blocked_terms: tuple[str, ...] = ()
    entity_terms: tuple[str, ...] = ()
    topic: str = "general"


@dataclass(frozen=True)
class WebSearchPlan:
    query: WebQuery
    queries: tuple[str, ...]
    answer_mode: str = "default"
    answer_instruction: str = ""
    require_freshness: bool = False
    strict_refusal: bool = False
    minimum_results: int = 1
    score_floor: float = 0.35
    debug_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    domain: str
    excerpt: str
    content: str
    provider_score: float | None = None
    rerank_score: float = 0.0
    final_score: float = 0.0
    published_at: str = ""
    trust_label: str = "unknown"
    freshness_label: str = "unknown"
    match_reason: str = ""
