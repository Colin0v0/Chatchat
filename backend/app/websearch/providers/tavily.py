from __future__ import annotations

from urllib.parse import urlparse

import httpx

from ...config import Settings
from ..types import WebQuery, WebSearchResult


class TavilyProvider:
    def __init__(self, settings: Settings):
        self._base_url = settings.web_search_base_url.rstrip("/")
        self._api_key = settings.web_search_api_key
        self._timeout = httpx.Timeout(settings.web_search_timeout_seconds, connect=10.0)
        self._max_results = max(1, settings.web_search_max_results)

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: WebQuery) -> list[WebSearchResult]:
        if not self.configured or not query.cleaned_query:
            return []

        payload: dict[str, object] = {
            "api_key": self._api_key,
            "query": query.cleaned_query,
            "topic": query.topic,
            "search_depth": "basic",
            "max_results": self._max_results,
            "include_raw_content": "markdown",
        }
        if query.include_domains:
            payload["include_domains"] = list(query.include_domains)
        if query.exclude_domains:
            payload["exclude_domains"] = list(query.exclude_domains)

        async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
            response = await client.post("/search", json=payload)
            if response.is_error:
                raise RuntimeError(_build_error_message(response))

        results: list[WebSearchResult] = []
        for item in response.json().get("results", []):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            title = str(item.get("title", "")).strip()
            if not url or not title:
                continue
            excerpt = str(item.get("content", "")).strip()
            raw_content = str(item.get("raw_content", "")).strip()
            score_raw = item.get("score")
            results.append(
                WebSearchResult(
                    title=title,
                    url=url,
                    domain=_domain_from_url(url),
                    excerpt=excerpt,
                    content=raw_content or excerpt,
                    provider_score=float(score_raw) if isinstance(score_raw, (int, float)) else None,
                    published_at=str(item.get("published_date", "") or item.get("published_at", "")).strip(),
                )
            )
        return results


def _build_error_message(response: httpx.Response) -> str:
    status = response.status_code
    reason = response.reason_phrase or "HTTP error"
    content_type = response.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            payload = response.json()
        except ValueError:
            return f"Tavily search request failed: {status} {reason}."
        detail = None
        if isinstance(payload, dict):
            detail = payload.get("detail") or payload.get("message") or payload.get("error")
        if isinstance(detail, str) and detail.strip():
            return f"Tavily search request failed: {status} {detail.strip()}."

    return f"Tavily search request failed: {status} {reason}."


def _domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower()
