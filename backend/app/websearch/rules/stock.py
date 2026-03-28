from __future__ import annotations

from dataclasses import replace

from ..types import WebQuery, WebSearchPlan
from .base import VerticalRule, dedupe_queries

STOCK_HINTS = ("stock", "shares", "ticker", "market cap", "eps", "pe", "price")
STOCK_PREFERRED_DOMAINS = (
    "finance.yahoo.com",
    "marketwatch.com",
    "companiesmarketcap.com",
    "nasdaq.com",
    "tradingview.com",
    "macrotrends.net",
)
STOCK_DISFAVORED_DOMAINS = ("reddit.com", "facebook.com", "instagram.com", "youtube.com")
STOCK_REQUIRED_TERMS = ("stock", "price", "market cap", "shares", "quote")
STOCK_BLOCKED_TERMS = ("fan", "forum", "prediction", "discussion")


class StockRule(VerticalRule):
    def __init__(self) -> None:
        super().__init__(intent="stock")

    def build_plan(self, query: WebQuery) -> WebSearchPlan:
        enriched = replace(
            query,
            preferred_domains=_merge(query.preferred_domains, STOCK_PREFERRED_DOMAINS),
            disfavored_domains=_merge(query.disfavored_domains, STOCK_DISFAVORED_DOMAINS),
            required_terms=_merge(query.required_terms, STOCK_REQUIRED_TERMS),
            blocked_terms=_merge(query.blocked_terms, STOCK_BLOCKED_TERMS),
        )
        subject = enriched.cleaned_query
        return WebSearchPlan(
            query=enriched,
            queries=dedupe_queries(
                subject,
                f"{subject} stock price",
                f"{subject} market cap",
                f"{subject} shares quote",
            ),
            answer_mode="stock",
            answer_instruction=(
                "For stock questions, separate real-time quote facts from commentary. "
                "List the latest price, change, ticker, and date if the sources contain them."
            ),
            require_freshness=True,
            strict_refusal=True,
            minimum_results=1,
            score_floor=0.48,
            debug_tags=("stock",),
        )


def _merge(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*left, *right]))
