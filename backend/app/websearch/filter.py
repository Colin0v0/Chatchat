from __future__ import annotations

from .types import WebSearchPlan, WebSearchResult

STRICT_DISFAVORED_INTENTS = {"music_entity_list", "music_lookup", "entity_list", "weather", "stock", "sports"}


def filter_results(plan: WebSearchPlan, results: list[WebSearchResult]) -> list[WebSearchResult]:
    return [result for result in results if _passes(plan, result)]


def _passes(plan: WebSearchPlan, result: WebSearchResult) -> bool:
    query = plan.query
    searchable_text = " ".join(
        part.strip().lower()
        for part in (result.title, result.excerpt, result.content[:600], result.url)
        if part.strip()
    )

    if query.required_terms and not _contains_any(searchable_text, query.required_terms):
        return False

    if query.disfavored_domains and _matches_domain(result.domain, query.disfavored_domains):
        if query.intent in STRICT_DISFAVORED_INTENTS:
            return False
        if not _contains_any(searchable_text, query.required_terms):
            return False

    if query.blocked_terms and _contains_any(searchable_text, query.blocked_terms):
        if not _matches_domain(result.domain, query.preferred_domains):
            return False

    if query.entity_terms and not _matches_entity_terms(searchable_text, query.entity_terms):
        if not _matches_domain(result.domain, query.preferred_domains):
            return False

    return True


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _matches_domain(domain: str, candidates: tuple[str, ...]) -> bool:
    normalized = domain.lower()
    return any(normalized == item or normalized.endswith(f".{item}") for item in candidates)


def _matches_entity_terms(text: str, entity_terms: tuple[str, ...]) -> bool:
    matches = sum(1 for term in entity_terms if term in text)
    if len(entity_terms) == 1:
        return matches == 1
    return matches >= max(1, len(entity_terms) // 2)
