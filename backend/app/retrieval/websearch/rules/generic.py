from __future__ import annotations

from ..types import WebQuery, WebSearchPlan
from .base import VerticalRule, dedupe_queries


class GenericRule(VerticalRule):
    def __init__(self) -> None:
        super().__init__(intent="general")

    def build_plan(self, query: WebQuery) -> WebSearchPlan:
        cleaned = query.cleaned_query.strip()
        return WebSearchPlan(
            query=query,
            queries=dedupe_queries(cleaned),
            answer_mode="default",
            answer_instruction="Answer directly from the most reliable sources. If evidence conflicts, say so plainly.",
            require_freshness=query.topic == "news",
            strict_refusal=False,
            minimum_results=1,
            score_floor=0.35,
            debug_tags=("generic",),
        )
