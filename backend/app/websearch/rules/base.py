from __future__ import annotations

from dataclasses import dataclass

from ..types import WebQuery, WebSearchPlan


@dataclass(frozen=True)
class VerticalRule:
    intent: str

    def build_plan(self, query: WebQuery) -> WebSearchPlan:
        raise NotImplementedError


def dedupe_queries(*queries: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(query.strip() for query in queries if query.strip()))
