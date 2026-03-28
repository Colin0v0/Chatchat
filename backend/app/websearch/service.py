from __future__ import annotations

from dataclasses import replace

from ..config import Settings
from ..retrieval.types import ContextEntry, ContextPayload, SourceItem
from .cache import WebSearchCache
from .dedupe import dedupe_results
from .extractor import extract_result_content
from .filter import filter_results
from .planner import build_search_plan
from .providers import TavilyProvider
from .reranker import WebLexicalReranker
from .types import WebSearchPlan, WebSearchResult

WEB_REFUSAL_MESSAGE = (
    "I could not find enough reliable web sources for this question. "
    "Try making the request more specific or add a site: filter."
)


class WebSearchService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._provider = TavilyProvider(settings)
        self._reranker = WebLexicalReranker()
        self._cache = WebSearchCache(ttl_seconds=300.0, max_entries=160)
        self._top_k = max(1, settings.web_search_top_k)
        self._min_score = max(0.0, settings.web_search_min_score)
        self._content_max_chars = max(400, settings.web_search_content_max_chars)

    def require_configuration(self) -> None:
        if not self._provider.configured:
            raise RuntimeError("Web search is not configured. Set WEB_SEARCH_API_KEY for Tavily first.")

    async def retrieve_context(self, query: str) -> ContextPayload:
        plan = await build_search_plan(query, self._settings)
        if not plan.queries:
            return ContextPayload()

        raw_results = await self._execute_plan(plan)
        if not raw_results:
            return ContextPayload(should_refuse=True, refusal_message=WEB_REFUSAL_MESSAGE, strategy_hint=_strategy_hint(plan))

        filtered_results = filter_results(plan, raw_results)
        if not filtered_results:
            return ContextPayload(should_refuse=True, refusal_message=WEB_REFUSAL_MESSAGE, strategy_hint=_strategy_hint(plan))

        ranked_results = self._reranker.rerank(plan, filtered_results)
        primary_results = ranked_results[: self._top_k]
        score_floor = max(self._min_score, plan.score_floor)
        if not primary_results or primary_results[0].final_score < score_floor:
            return ContextPayload(should_refuse=True, refusal_message=WEB_REFUSAL_MESSAGE, strategy_hint=_strategy_hint(plan))
        if plan.strict_refusal and len(primary_results) < plan.minimum_results:
            return ContextPayload(should_refuse=True, refusal_message=WEB_REFUSAL_MESSAGE, strategy_hint=_strategy_hint(plan))

        sources: list[SourceItem] = []
        entries: list[ContextEntry] = []
        for result in primary_results:
            source = SourceItem(
                type="web",
                path=result.url,
                excerpt=_truncate_excerpt(result.excerpt),
                score=result.final_score,
                title=result.title,
                url=result.url,
                domain=result.domain,
                published_at=result.published_at,
                trust=result.trust_label,
                freshness=result.freshness_label,
                match_reason=result.match_reason,
            )
            sources.append(source)
            entries.append(
                ContextEntry(
                    source=source,
                    content=extract_result_content(plan, result, self._content_max_chars),
                )
            )

        return ContextPayload(
            entries=entries,
            sources=sources,
            instructions=(plan.answer_instruction,) if plan.answer_instruction else (),
            strategy_hint=_strategy_hint(plan),
            debug={
                "intent": plan.query.intent,
                "queries": list(plan.queries),
                "answer_mode": plan.answer_mode,
                "tags": list(plan.debug_tags),
            },
        )

    async def _execute_plan(self, plan: WebSearchPlan) -> list[WebSearchResult]:
        results: list[WebSearchResult] = []
        for search_query in plan.queries:
            cache_key = self._cache_key(plan, search_query)
            cached = self._cache.get(cache_key)
            if cached is not None:
                results.extend(cached)
                continue

            provider_query = replace(plan.query, cleaned_query=search_query)
            fetched = await self._provider.search(provider_query)
            self._cache.set(cache_key, fetched)
            results.extend(fetched)
        return dedupe_results(results)

    def _cache_key(self, plan: WebSearchPlan, search_query: str) -> str:
        include_domains = ",".join(plan.query.include_domains)
        exclude_domains = ",".join(plan.query.exclude_domains)
        return f"{plan.query.intent}|{plan.query.topic}|{search_query}|{include_domains}|{exclude_domains}"


def _strategy_hint(plan: WebSearchPlan) -> str:
    if plan.require_freshness:
        return "web_primary"
    if plan.answer_mode in {"song_list", "song_lookup"}:
        return "web_primary"
    return "balanced"


def _truncate_excerpt(content: str, limit: int = 280) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."
