from __future__ import annotations

import re

from .classifier import NEWS_HINTS
from .types import WebQuery

SITE_PATTERN = re.compile(r'(?<!\S)(-?site:)("[^"]+"|\S+)')
CJK_PATTERN = re.compile(r'[\u3400-\u9fff]')


def parse_web_query(query: str) -> WebQuery:
    include_domains: list[str] = []
    exclude_domains: list[str] = []

    def replace_site(match: re.Match[str]) -> str:
        prefix = match.group(1)
        raw_value = match.group(2).strip().strip('"')
        domain = raw_value.removeprefix('https://').removeprefix('http://').strip('/').lower()
        if not domain:
            return ' '
        if prefix.startswith('-'):
            exclude_domains.append(domain)
        else:
            include_domains.append(domain)
        return ' '

    cleaned_query = SITE_PATTERN.sub(replace_site, query)
    cleaned_query = ' '.join(cleaned_query.split())
    topic = 'news' if _looks_like_news(cleaned_query) else 'general'
    return WebQuery(
        raw_query=query,
        cleaned_query=cleaned_query,
        include_domains=tuple(dict.fromkeys(include_domains)),
        exclude_domains=tuple(dict.fromkeys(exclude_domains)),
        topic=topic,
    )


def contains_cjk(text: str) -> bool:
    return bool(CJK_PATTERN.search(text))


def _looks_like_news(query: str) -> bool:
    normalized = query.lower()
    return any(hint in normalized for hint in NEWS_HINTS)
