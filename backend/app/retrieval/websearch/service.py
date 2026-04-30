from __future__ import annotations

import asyncio
from dataclasses import asdict
from dataclasses import replace

from ...cache import build_cache_key, get_json, set_json
from ...core.config import Settings
from ..language import prefers_simplified_chinese
from ..types import ContextEntry, ContextPayload, SourceItem
from .dedupe import dedupe_results
from .extractor import extract_result_content
from .filter import filter_results
from .planner import build_search_plan
from .providers import DashScopeWebSearchProvider
from .reranker import WebLexicalReranker
from .types import WebSearchPlan, WebSearchResult

WEB_REFUSAL_MESSAGE = (
    "I could not find enough reliable web sources for this question. "
    "Try making the request more specific or add a site: filter."
)
WEB_REFUSAL_MESSAGE_ZH = "我没有找到足够可靠的网页来源来回答这个问题。可以把问题范围收窄，或指定站点。"
WEB_QUERY_TOO_SHORT_REFUSAL_MESSAGE = (
    "Search query is too short."
)
WEB_QUERY_TOO_SHORT_REFUSAL_MESSAGE_ZH = "搜索问题太短，无法形成有效的网页搜索词。"


class WebSearchService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._provider = DashScopeWebSearchProvider(settings)
        self._reranker = WebLexicalReranker()
        self._top_k = max(1, settings.web_search_top_k)
        self._min_score = max(0.0, settings.web_search_min_score)
        self._content_max_chars = max(400, settings.web_search_content_max_chars)
        self._cache_ttl_seconds = max(1, int(getattr(settings, "cache_web_search_ttl_seconds", 900)))

    def require_configuration(self) -> None:
        if not self._provider.configured:
            raise RuntimeError("Web search is not configured. Set DASHSCOPE_API_KEY or WEB_SEARCH_API_KEY first.")

    async def retrieve_context(self, query: str) -> ContextPayload:
        try:
            plan = await build_search_plan(query, self._settings)
        except Exception as exc:
            # 搜索计划构建失败（如翻译/网络错误）时不拒绝用户，静默降级为空上下文，让模型直接回答。
            return ContextPayload(debug={"error": str(exc)})

        if not plan.queries:
            return ContextPayload()
        if _query_is_too_short(plan):
            return ContextPayload(
                should_refuse=True,
                refusal_message=_short_query_refusal_message(query),
                strategy_hint=_strategy_hint(plan),
                debug=_plan_debug(plan),
            )

        try:
            raw_results = await self._execute_plan(plan)
        except Exception as exc:
            # 搜索执行失败（如网络错误）时不拒绝用户，静默降级为空上下文。
            return ContextPayload(debug={"error": str(exc)})

        if not raw_results:
            return ContextPayload(debug={"rag_ready": True, "rag_reason": "no_raw_results", **_plan_debug(plan)})

        filtered_results = filter_results(plan, raw_results)
        if not filtered_results:
            return ContextPayload(debug={"rag_ready": True, "rag_reason": "no_filtered_results", **_plan_debug(plan)})

        ranked_results = self._reranker.rerank(plan, filtered_results)
        # 多实体新鲜度问题需要更多网页片段，否则模型会用旧知识补齐未覆盖公司。
        primary_limit = max(self._top_k, plan.minimum_results)
        primary_results = ranked_results[:primary_limit]
        score_floor = max(self._min_score, plan.score_floor)
        if not primary_results or primary_results[0].final_score < score_floor:
            return ContextPayload(debug={"rag_ready": True, "rag_reason": "low_score", **_plan_debug(plan)})
        if plan.strict_refusal and len(primary_results) < plan.minimum_results:
            return ContextPayload(debug={"rag_ready": True, "rag_reason": "insufficient_results", **_plan_debug(plan)})

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
            debug=_plan_debug(plan),
        )

    async def _execute_plan(self, plan: WebSearchPlan) -> list[WebSearchResult]:
        results: list[WebSearchResult] = []
        uncached_queries: list[str] = []
        for search_query in plan.queries:
            cache_key = self._cache_key(plan, search_query)
            cached = await get_json(self._settings, cache_key)
            if cached is not None:
                results.extend(_results_from_cached_json(cached))
                continue
            uncached_queries.append(search_query)

        if uncached_queries:
            fetched_batches = await asyncio.gather(
                *[
                    self._provider.search(replace(plan.query, cleaned_query=search_query))
                    for search_query in uncached_queries
                ]
            )
            for search_query, fetched in zip(uncached_queries, fetched_batches):
                cache_key = self._cache_key(plan, search_query)
                await set_json(
                    self._settings,
                    cache_key,
                    [asdict(result) for result in fetched],
                    ttl_seconds=self._cache_ttl_seconds,
                )
                results.extend(fetched)
        return dedupe_results(results)

    def _cache_key(self, plan: WebSearchPlan, search_query: str) -> str:
        return build_cache_key(
            self._settings,
            namespace="web_search",
            version=1,
            payload={
                "provider": getattr(self._settings, "web_search_provider", ""),
                "model": getattr(self._settings, "web_search_model", ""),
                "strategy": getattr(self._settings, "web_search_strategy", ""),
                "max_results": getattr(self._settings, "web_search_max_results", 0),
                "intent": plan.query.intent,
                "topic": plan.query.topic,
                "search_query": search_query,
                "include_domains": list(plan.query.include_domains),
                "exclude_domains": list(plan.query.exclude_domains),
                "required_terms": list(plan.query.required_terms),
                "blocked_terms": list(plan.query.blocked_terms),
            },
        )


def _results_from_cached_json(payload: object) -> list[WebSearchResult]:
    if not isinstance(payload, list):
        raise RuntimeError("Web search cache entry must be a list.")

    results: list[WebSearchResult] = []
    for item in payload:
        if not isinstance(item, dict):
            raise RuntimeError("Web search cache entry contains a non-object item.")
        results.append(
            WebSearchResult(
                title=str(item.get("title", "")),
                url=str(item.get("url", "")),
                domain=str(item.get("domain", "")),
                excerpt=str(item.get("excerpt", "")),
                content=str(item.get("content", "")),
                provider_score=_optional_float(item.get("provider_score")),
                rerank_score=_required_float(item.get("rerank_score"), field_name="rerank_score"),
                final_score=_required_float(item.get("final_score"), field_name="final_score"),
                published_at=str(item.get("published_at", "")),
                trust_label=str(item.get("trust_label", "unknown")),
                freshness_label=str(item.get("freshness_label", "unknown")),
                match_reason=str(item.get("match_reason", "")),
            )
        )
    return results


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return _required_float(value, field_name="provider_score")


def _required_float(value: object, *, field_name: str) -> float:
    if isinstance(value, bool):
        raise RuntimeError(f"Web search cache field {field_name} must be numeric.")
    try:
        return float(value if value is not None else 0.0)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Web search cache field {field_name} must be numeric.") from exc


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


def _query_is_too_short(plan: WebSearchPlan) -> bool:
    return any(len(search_query.strip()) < 2 for search_query in plan.queries)


def _refusal_message(query: str) -> str:
    if prefers_simplified_chinese(query):
        return WEB_REFUSAL_MESSAGE_ZH
    return WEB_REFUSAL_MESSAGE


def _short_query_refusal_message(query: str) -> str:
    if prefers_simplified_chinese(query):
        return WEB_QUERY_TOO_SHORT_REFUSAL_MESSAGE_ZH
    return WEB_QUERY_TOO_SHORT_REFUSAL_MESSAGE


def _plan_debug(plan: WebSearchPlan) -> dict[str, object]:
    return {
        "intent": plan.query.intent,
        "queries": list(plan.queries),
        "answer_mode": plan.answer_mode,
        "tags": list(plan.debug_tags),
    }
