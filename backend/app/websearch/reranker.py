from __future__ import annotations

import re

from .trust import freshness_label, freshness_score, trust_label, trust_score
from .types import WebSearchPlan, WebSearchResult

TOKEN_PATTERN = re.compile(r"[a-z0-9\u4e00-\u9fff]{2,}", re.IGNORECASE)


class WebLexicalReranker:
    def score(self, plan: WebSearchPlan, result: WebSearchResult) -> WebSearchResult:
        query_tokens = set(_tokenize(plan.query.cleaned_query))
        title_tokens = set(_tokenize(result.title))
        excerpt_tokens = set(_tokenize(result.excerpt))
        content_tokens = set(_tokenize(result.content[:500]))
        domain_tokens = set(_tokenize(result.domain))

        lexical_score = 0.0
        if query_tokens:
            lexical_score = (
                _overlap_ratio(query_tokens, title_tokens) * 0.38
                + _overlap_ratio(query_tokens, excerpt_tokens) * 0.22
                + _overlap_ratio(query_tokens, content_tokens) * 0.20
                + _overlap_ratio(query_tokens, domain_tokens) * 0.05
                + _required_terms_bonus(result, plan) * 0.10
                + _entity_bonus(result, plan) * 0.05
            )

        provider_score = _normalize_provider_score(result.provider_score)
        trust_value = trust_score(result.domain, plan.query.preferred_domains, plan.query.disfavored_domains)
        freshness_value = freshness_score(result.published_at, plan.require_freshness)
        final_score = (
            provider_score * 0.35
            + min(1.0, lexical_score) * 0.30
            + trust_value * 0.25
            + freshness_value * 0.10
        )
        trust_text = trust_label(result.domain, plan.query.preferred_domains, plan.query.disfavored_domains)
        freshness_text = freshness_label(result.published_at, plan.require_freshness)
        match_reason = _match_reason(result, plan, trust_text, freshness_text)
        return WebSearchResult(
            title=result.title,
            url=result.url,
            domain=result.domain,
            excerpt=result.excerpt,
            content=result.content,
            provider_score=result.provider_score,
            rerank_score=min(1.0, lexical_score),
            final_score=max(0.0, min(1.0, final_score)),
            published_at=result.published_at,
            trust_label=trust_text,
            freshness_label=freshness_text,
            match_reason=match_reason,
        )

    def rerank(self, plan: WebSearchPlan, results: list[WebSearchResult]) -> list[WebSearchResult]:
        reranked = [self.score(plan, result) for result in results]
        return sorted(reranked, key=lambda item: item.final_score, reverse=True)


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left)


def _normalize_provider_score(score: float | None) -> float:
    if score is None:
        return 0.0
    return max(0.0, min(float(score), 1.0))


def _required_terms_bonus(result: WebSearchResult, plan: WebSearchPlan) -> float:
    if not plan.query.required_terms:
        return 0.0
    searchable = _searchable_text(result)
    matches = sum(1 for term in plan.query.required_terms if term in searchable)
    return min(1.0, matches / max(1, len(plan.query.required_terms)))


def _entity_bonus(result: WebSearchResult, plan: WebSearchPlan) -> float:
    if not plan.query.entity_terms:
        return 0.0
    searchable = _searchable_text(result)
    matches = sum(1 for term in plan.query.entity_terms if term in searchable)
    return min(1.0, matches / max(1, len(plan.query.entity_terms)))


def _searchable_text(result: WebSearchResult) -> str:
    return " ".join(part.strip().lower() for part in (result.title, result.excerpt, result.content[:500], result.url) if part.strip())


def _match_reason(result: WebSearchResult, plan: WebSearchPlan, trust_text: str, freshness_text: str) -> str:
    reasons: list[str] = []
    searchable = _searchable_text(result)
    required_matches = [term for term in plan.query.required_terms if term in searchable]
    if required_matches:
        reasons.append(f"matched {', '.join(required_matches[:3])}")
    if trust_text != "standard":
        reasons.append(f"trust {trust_text}")
    if freshness_text not in {"unknown", "missing"}:
        reasons.append(f"freshness {freshness_text}")
    return "; ".join(reasons)
