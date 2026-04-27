import asyncio
import time
import unittest
from types import SimpleNamespace

from app.retrieval.websearch.service import (
    WEB_QUERY_TOO_SHORT_REFUSAL_MESSAGE,
    WebSearchService,
)
from app.retrieval.websearch.types import WebQuery, WebSearchPlan, WebSearchResult


def make_settings():
    return SimpleNamespace(
        web_search_top_k=4,
        web_search_min_score=0.35,
        web_search_content_max_chars=1600,
        web_search_provider="dashscope",
        web_search_base_url="https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
        web_search_api_key="test-key",
        web_search_timeout_seconds=20.0,
        web_search_model="qwen-plus",
        web_search_strategy="turbo",
        web_search_forced=True,
        web_search_enable_source=True,
        web_search_enable_citation=True,
        web_search_citation_format="[ref_<number>]",
        web_search_max_results=5,
        web_search_translation_model="codex:gpt-5.2",
        dashscope_api_key="",
    )


class _NeverCalledProvider:
    configured = True

    async def search(self, query):
        raise AssertionError(f"provider.search should not be called for short query: {query.cleaned_query!r}")


class _ConcurrentProvider:
    configured = True

    def __init__(self):
        self.calls = []

    async def search(self, query):
        self.calls.append(query.cleaned_query)
        await asyncio.sleep(0.1)
        return [
            WebSearchResult(
                title=f"Result for {query.cleaned_query}",
                url=f"https://example.com/{query.cleaned_query}",
                domain="example.com",
                excerpt=f"Excerpt for {query.cleaned_query}",
                content=f"Content for {query.cleaned_query}",
                provider_score=0.9,
            )
        ]


class WebSearchServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_query_refuses_before_calling_provider(self):
        service = WebSearchService(make_settings())
        service._provider = _NeverCalledProvider()

        payload = await service.retrieve_context("1")

        self.assertTrue(payload.should_refuse)
        self.assertEqual(payload.refusal_message, WEB_QUERY_TOO_SHORT_REFUSAL_MESSAGE)

    async def test_execute_plan_runs_uncached_queries_concurrently(self):
        service = WebSearchService(make_settings())
        provider = _ConcurrentProvider()
        service._provider = provider
        plan = WebSearchPlan(
            query=WebQuery(raw_query="alpha beta", cleaned_query="alpha beta"),
            queries=("alpha", "beta"),
        )

        started_at = time.perf_counter()
        results = await service._execute_plan(plan)
        elapsed = time.perf_counter() - started_at

        self.assertEqual(len(results), 2)
        self.assertCountEqual(provider.calls, ["alpha", "beta"])
        self.assertLess(elapsed, 0.18)


if __name__ == "__main__":
    unittest.main()
