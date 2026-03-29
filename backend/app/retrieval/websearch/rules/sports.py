from __future__ import annotations

from dataclasses import replace

from ..types import WebQuery, WebSearchPlan
from .base import VerticalRule, dedupe_queries

SPORTS_PREFERRED_DOMAINS = (
    "espn.com",
    "nba.com",
    "nfl.com",
    "mlb.com",
    "nhl.com",
    "fifa.com",
    "uefa.com",
    "flashscore.com",
    "sofascore.com",
)
SPORTS_DISFAVORED_DOMAINS = ("reddit.com", "facebook.com", "instagram.com", "youtube.com")
SPORTS_REQUIRED_TERMS = ("score", "schedule", "standings", "game", "match", "stats")
SPORTS_BLOCKED_TERMS = ("rumor", "discussion", "forum")


class SportsRule(VerticalRule):
    def __init__(self) -> None:
        super().__init__(intent="sports")

    def build_plan(self, query: WebQuery) -> WebSearchPlan:
        enriched = replace(
            query,
            preferred_domains=_merge(query.preferred_domains, SPORTS_PREFERRED_DOMAINS),
            disfavored_domains=_merge(query.disfavored_domains, SPORTS_DISFAVORED_DOMAINS),
            required_terms=_merge(query.required_terms, SPORTS_REQUIRED_TERMS),
            blocked_terms=_merge(query.blocked_terms, SPORTS_BLOCKED_TERMS),
        )
        subject = enriched.cleaned_query
        return WebSearchPlan(
            query=enriched,
            queries=dedupe_queries(
                subject,
                f"{subject} score",
                f"{subject} schedule",
                f"{subject} standings",
            ),
            answer_mode="sports",
            answer_instruction=(
                "For sports questions, prefer scoreboard, schedule, standings, or official league pages. "
                "Include the event date when available."
            ),
            require_freshness=True,
            strict_refusal=True,
            minimum_results=1,
            score_floor=0.46,
            debug_tags=("sports",),
        )


def _merge(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*left, *right]))
