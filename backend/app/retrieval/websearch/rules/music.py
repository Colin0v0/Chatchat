from __future__ import annotations

from dataclasses import replace

from ..types import WebQuery, WebSearchPlan
from .base import VerticalRule, dedupe_queries

MUSIC_PREFERRED_DOMAINS = (
    "wikipedia.org",
    "genius.com",
    "spotify.com",
    "music.apple.com",
    "allmusic.com",
    "secondhandsongs.com",
)
MUSIC_DISFAVORED_DOMAINS = (
    "reddit.com",
    "quora.com",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
)
MUSIC_LIST_REQUIRED_TERMS = ("song", "songs", "discography", "album", "albums", "track", "tracks")
MUSIC_LOOKUP_REQUIRED_TERMS = ("song", "artist", "singer", "written", "writer", "performed", "lyrics")
MUSIC_BLOCKED_TERMS = ("popular", "popularity", "great", "greatest", "phenomenon", "why")


class MusicEntityListRule(VerticalRule):
    def __init__(self) -> None:
        super().__init__(intent="music_entity_list")

    def build_plan(self, query: WebQuery) -> WebSearchPlan:
        enriched = _with_music_policy(query, required_terms=MUSIC_LIST_REQUIRED_TERMS)
        subject = enriched.cleaned_query
        return WebSearchPlan(
            query=enriched,
            queries=dedupe_queries(
                subject,
                subject.replace("songs list discography", "songs list").strip(),
                subject.replace("songs list discography", "discography").strip(),
                f"{subject.split(' songs', 1)[0]} spotify songs",
            ),
            answer_mode="song_list",
            answer_instruction=(
                "For song-list questions, prefer an explicit song or discography list. "
                "Return a concise Markdown list grouped by albums or eras when possible."
            ),
            require_freshness=False,
            strict_refusal=True,
            minimum_results=2,
            score_floor=0.42,
            debug_tags=("music", "list"),
        )


class MusicLookupRule(VerticalRule):
    def __init__(self) -> None:
        super().__init__(intent="music_lookup")

    def build_plan(self, query: WebQuery) -> WebSearchPlan:
        enriched = _with_music_policy(query, required_terms=MUSIC_LOOKUP_REQUIRED_TERMS)
        subject = enriched.cleaned_query
        return WebSearchPlan(
            query=enriched,
            queries=dedupe_queries(
                subject,
                subject.replace("artist", "writer").strip(),
                subject.replace("artist", "performed by").strip(),
            ),
            answer_mode="song_lookup",
            answer_instruction=(
                "For song attribution questions, identify the song, artist, and writer separately if the evidence supports it. "
                "If multiple songs share the same title, say that clearly."
            ),
            require_freshness=False,
            strict_refusal=True,
            minimum_results=2,
            score_floor=0.40,
            debug_tags=("music", "lookup"),
        )


def _with_music_policy(query: WebQuery, *, required_terms: tuple[str, ...]) -> WebQuery:
    return replace(
        query,
        preferred_domains=_merge(query.preferred_domains, MUSIC_PREFERRED_DOMAINS),
        disfavored_domains=_merge(query.disfavored_domains, MUSIC_DISFAVORED_DOMAINS),
        required_terms=_merge(query.required_terms, required_terms),
        blocked_terms=_merge(query.blocked_terms, MUSIC_BLOCKED_TERMS),
    )


def _merge(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys([*left, *right]))
