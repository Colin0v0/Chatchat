from __future__ import annotations

from urllib.parse import urlparse

from .types import WebSearchResult


def dedupe_results(results: list[WebSearchResult]) -> list[WebSearchResult]:
    unique_by_url: dict[tuple[str, str], WebSearchResult] = {}
    for result in results:
        key = (_normalize_url(result.url), _normalize_title(result.title))
        previous = unique_by_url.get(key)
        if previous is None or (result.provider_score or 0.0) > (previous.provider_score or 0.0):
            unique_by_url[key] = result

    unique_by_title: dict[tuple[str, str], WebSearchResult] = {}
    for result in unique_by_url.values():
        key = (result.domain.lower(), _normalize_title(result.title))
        previous = unique_by_title.get(key)
        if previous is None or (result.provider_score or 0.0) > (previous.provider_score or 0.0):
            unique_by_title[key] = result
    return list(unique_by_title.values())


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.netloc.lower()}{path}"


def _normalize_title(title: str) -> str:
    return " ".join(title.lower().split())
