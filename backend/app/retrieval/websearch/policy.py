from __future__ import annotations

from dataclasses import replace

from .types import WebQuery

CURRENT_WEATHER_HINTS = ("today", "current", "now", "\u4eca\u5929", "\u73b0\u5728")
CURRENT_WEATHER_BLOCKED_TERMS = ("month", "monthly", "climate", "historical", "history")

INTENT_POLICIES = {
    "music_entity_list": {
        "preferred_domains": (
            "wikipedia.org",
            "spotify.com",
            "music.apple.com",
            "genius.com",
            "allmusic.com",
            "secondhandsongs.com",
        ),
        "disfavored_domains": (
            "reddit.com",
            "quora.com",
            "facebook.com",
            "instagram.com",
            "x.com",
            "twitter.com",
            "tiktok.com",
        ),
        "required_terms": ("song", "songs", "discography", "album", "albums", "track", "tracks"),
        "blocked_terms": ("popular", "popularity", "great", "greatest", "phenomenon", "why"),
    },
    "music_lookup": {
        "preferred_domains": (
            "wikipedia.org",
            "genius.com",
            "spotify.com",
            "music.apple.com",
            "allmusic.com",
            "secondhandsongs.com",
        ),
        "disfavored_domains": ("reddit.com", "quora.com", "facebook.com", "instagram.com"),
        "required_terms": ("song", "artist", "singer", "written", "writer", "performed", "lyrics"),
        "blocked_terms": ("popular", "popularity", "great"),
    },
    "weather": {
        "preferred_domains": (
            "weather.com",
            "weatherapi.com",
            "accuweather.com",
            "timeanddate.com",
            "weather25.com",
            "forecast.weather.gov",
        ),
        "disfavored_domains": ("reddit.com", "facebook.com", "instagram.com"),
        "required_terms": ("weather", "forecast", "temperature"),
        "blocked_terms": ("history", "popular"),
    },
    "entity_list": {
        "preferred_domains": ("wikipedia.org",),
        "disfavored_domains": ("reddit.com", "quora.com", "facebook.com", "instagram.com"),
        "required_terms": ("list",),
        "blocked_terms": ("popular", "great", "why"),
    },
}


def apply_domain_policy(query: WebQuery) -> WebQuery:
    policy = INTENT_POLICIES.get(query.intent)
    if policy is None:
        return query

    planned = replace(
        query,
        preferred_domains=_merge_values(query.preferred_domains, policy["preferred_domains"]),
        disfavored_domains=_merge_values(query.disfavored_domains, policy["disfavored_domains"]),
        required_terms=_merge_values(query.required_terms, policy["required_terms"]),
        blocked_terms=_merge_values(query.blocked_terms, policy["blocked_terms"]),
    )

    if planned.intent == "weather" and _looks_like_current_weather(planned.raw_query):
        planned = replace(planned, blocked_terms=_merge_values(planned.blocked_terms, CURRENT_WEATHER_BLOCKED_TERMS))

    return planned


def _looks_like_current_weather(query: str) -> bool:
    normalized = query.lower()
    return any(hint in normalized for hint in CURRENT_WEATHER_HINTS)


def _merge_values(existing: tuple[str, ...], extra: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*existing, *extra]))
