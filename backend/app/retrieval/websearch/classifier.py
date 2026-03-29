from __future__ import annotations

import re

NEWS_HINTS = (
    "latest",
    "recent",
    "news",
    "update",
    "breaking",
    "\u6700\u65b0",
    "\u65b0\u95fb",
    "\u66f4\u65b0",
    "\u53d1\u5e03",
)
WEATHER_HINTS = (
    "weather",
    "forecast",
    "temperature",
    "rain",
    "snow",
    "humidity",
    "\u5929\u6c14",
    "\u6c14\u6e29",
    "\u6e29\u5ea6",
    "\u4e0b\u96e8",
    "\u4e0b\u96ea",
    "\u6e7f\u5ea6",
    "\u9884\u62a5",
)
LIST_HINTS = (
    "list",
    "all",
    "\u6709\u54ea\u4e9b",
    "\u6709\u4ec0\u4e48",
    "\u5217\u8868",
    "\u76ee\u5f55",
    "\u90fd\u6709\u54ea\u4e9b",
    "\u4f5c\u54c1",
)
MUSIC_HINTS = (
    "song",
    "songs",
    "track",
    "tracks",
    "album",
    "albums",
    "discography",
    "music",
    "\u6b4c",
    "\u6b4c\u66f2",
    "\u4e13\u8f91",
    "\u5531\u7247",
    "\u5355\u66f2",
)
MUSIC_LOOKUP_HINTS = (
    "who wrote",
    "written by",
    "performed by",
    "singer",
    "artist",
    "\u8c01\u5531",
    "\u8c01\u7684\u6b4c",
    "\u6f14\u5531",
    "\u4f5c\u8bcd",
    "\u4f5c\u66f2",
)
STOCK_HINTS = (
    "stock",
    "shares",
    "ticker",
    "market cap",
    "market value",
    "eps",
    "pe",
    "p/e",
    "price",
    "\u80a1\u4ef7",
    "\u5e02\u503c",
    "\u80a1\u7968",
    "\u80a1\u4efd",
    "\u8d22\u62a5",
)
SPORTS_HINTS = (
    "score",
    "schedule",
    "standings",
    "match",
    "game",
    "fixture",
    "player stats",
    "nba",
    "nfl",
    "mlb",
    "nhl",
    "epl",
    "\u6bd4\u5206",
    "\u8d5b\u7a0b",
    "\u79ef\u5206",
    "\u6392\u540d",
    "\u6bd4\u8d5b",
)

LATIN_SUBJECT_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9'&.+-]*(?:\s+[A-Za-z][A-Za-z0-9'&.+-]*)*")


def classify_web_intent(query: str) -> str:
    normalized = query.lower().strip()
    if not normalized:
        return "general"

    if _contains_hint(normalized, WEATHER_HINTS):
        return "weather"
    if _contains_hint(normalized, STOCK_HINTS):
        return "stock"
    if _contains_hint(normalized, SPORTS_HINTS):
        return "sports"
    if _contains_hint(normalized, NEWS_HINTS):
        return "news"
    if _looks_like_music_entity_list(normalized):
        return "music_entity_list"
    if _looks_like_music_lookup(normalized):
        return "music_lookup"
    if _looks_like_entity_list(normalized):
        return "entity_list"
    return "general"


def extract_latin_subject(query: str) -> str:
    matches = [match.group(0).strip() for match in LATIN_SUBJECT_PATTERN.finditer(query)]
    matches = [match for match in matches if match]
    if not matches:
        return ""
    return " ".join(max(matches, key=len).split())


def _looks_like_music_entity_list(query: str) -> bool:
    return _contains_hint(query, MUSIC_HINTS) and _contains_hint(query, LIST_HINTS)


def _looks_like_music_lookup(query: str) -> bool:
    return _contains_hint(query, MUSIC_LOOKUP_HINTS) and _contains_hint(query, MUSIC_HINTS)


def _looks_like_entity_list(query: str) -> bool:
    return _contains_hint(query, LIST_HINTS)


def _contains_hint(query: str, hints: tuple[str, ...]) -> bool:
    return any(hint in query for hint in hints)
