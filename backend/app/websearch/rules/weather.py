from __future__ import annotations

from dataclasses import replace

from ..types import WebQuery, WebSearchPlan
from .base import VerticalRule, dedupe_queries

CURRENT_WEATHER_HINTS = ("today", "current", "now", "\u4eca\u5929", "\u73b0\u5728")
WEATHER_PREFERRED_DOMAINS = (
    "weather.com",
    "weatherapi.com",
    "accuweather.com",
    "timeanddate.com",
    "forecast.weather.gov",
    "weather.gc.ca",
)
WEATHER_DISFAVORED_DOMAINS = (
    "reddit.com",
    "facebook.com",
    "instagram.com",
    "traveloka.com",
)
WEATHER_REQUIRED_TERMS = ("weather", "forecast", "temperature")
WEATHER_BLOCKED_TERMS = ("history", "historical", "popular")
CURRENT_WEATHER_BLOCKED_TERMS = ("month", "monthly", "climate", "march", "april", "may")


class WeatherRule(VerticalRule):
    def __init__(self) -> None:
        super().__init__(intent="weather")

    def build_plan(self, query: WebQuery) -> WebSearchPlan:
        enriched = replace(
            query,
            preferred_domains=_merge(query.preferred_domains, WEATHER_PREFERRED_DOMAINS),
            disfavored_domains=_merge(query.disfavored_domains, WEATHER_DISFAVORED_DOMAINS),
            required_terms=_merge(query.required_terms, WEATHER_REQUIRED_TERMS),
            blocked_terms=_merge(
                query.blocked_terms,
                CURRENT_WEATHER_BLOCKED_TERMS if _looks_like_current_weather(query.raw_query) else WEATHER_BLOCKED_TERMS,
            ),
        )
        subject = enriched.cleaned_query
        city = subject.replace("weather", "").replace("forecast", "").strip()
        return WebSearchPlan(
            query=enriched,
            queries=dedupe_queries(
                subject,
                f"{city} current weather".strip(),
                f"{city} temperature weather".strip(),
            ),
            answer_mode="weather",
            answer_instruction=(
                "For weather questions, summarize current conditions, temperature, precipitation, and timing in a compact Markdown briefing. "
                "If the sources are monthly climate pages rather than current conditions, say that the evidence is weak."
            ),
            require_freshness=True,
            strict_refusal=True,
            minimum_results=1,
            score_floor=0.45,
            debug_tags=("weather",),
        )


def _looks_like_current_weather(query: str) -> bool:
    normalized = query.lower()
    return any(hint in normalized for hint in CURRENT_WEATHER_HINTS)


def _merge(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*left, *right]))
