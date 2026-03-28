from __future__ import annotations

from dataclasses import replace
import re

from .classifier import extract_latin_subject
from .types import WebQuery

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'.&+-]*")
ENTITY_STOPWORDS = {
    "all",
    "album",
    "albums",
    "artist",
    "artists",
    "discography",
    "forecast",
    "latest",
    "list",
    "market",
    "music",
    "news",
    "price",
    "recent",
    "schedule",
    "score",
    "shares",
    "singer",
    "song",
    "songs",
    "standings",
    "stock",
    "temperature",
    "today",
    "track",
    "tracks",
    "weather",
    "what",
    "who",
    "wrote",
    "written",
}


def rewrite_web_query(query: WebQuery) -> WebQuery:
    base_query = (query.translated_query or query.cleaned_query).strip()
    if not base_query:
        return query

    rewritten = _rewrite_by_intent(query, base_query)
    entity_terms = tuple(_extract_entity_terms(rewritten))
    return replace(query, cleaned_query=rewritten, entity_terms=entity_terms)


def _rewrite_by_intent(query: WebQuery, base_query: str) -> str:
    latin_subject = extract_latin_subject(query.raw_query)
    if query.intent == "music_entity_list":
        subject = latin_subject or base_query
        return _append_unique_terms(subject, ("songs", "list", "discography"))
    if query.intent == "music_lookup":
        return _append_unique_terms(latin_subject or base_query, ("song", "artist"))
    if query.intent == "entity_list":
        return _append_unique_terms(latin_subject or base_query, ("list",))
    if query.intent == "weather":
        return _append_unique_terms(base_query, ("weather",))
    if query.intent == "stock":
        return _append_unique_terms(latin_subject or base_query, ("stock", "price"))
    if query.intent == "sports":
        return _append_unique_terms(base_query, ("score",))
    if query.intent == "news":
        return _append_unique_terms(base_query, ("latest",))
    return " ".join(base_query.split())


def _append_unique_terms(query: str, terms: tuple[str, ...]) -> str:
    existing_terms = {token.lower() for token in TOKEN_PATTERN.findall(query)}
    combined = [query.strip()]
    for term in terms:
        if term.lower() not in existing_terms:
            combined.append(term)
    return " ".join(part for part in combined if part).strip()


def _extract_entity_terms(query: str) -> list[str]:
    terms: list[str] = []
    for token in TOKEN_PATTERN.findall(query):
        normalized = token.lower()
        if normalized in ENTITY_STOPWORDS or normalized.isdigit() or len(normalized) < 3:
            continue
        terms.append(normalized)
    return list(dict.fromkeys(terms))
