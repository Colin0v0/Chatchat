from __future__ import annotations

import re

from .text import normalize_path_fragment, normalize_tag
from .types import QueryFilters, RagChunk

FILTER_PATTERN = re.compile(
    r'(?<!\S)(?P<kind>folder|path|tag):(?P<value>"[^"]+"|\'[^\']+\'|\S+)',
    re.IGNORECASE,
)


def parse_query_filters(raw_query: str) -> QueryFilters:
    folders: list[str] = []
    paths: list[str] = []
    tags: list[str] = []

    def replace(match: re.Match[str]) -> str:
        kind = match.group("kind").lower()
        value = match.group("value")
        if kind == "tag":
            normalized = normalize_tag(value)
            if normalized:
                tags.append(normalized)
        else:
            normalized = normalize_path_fragment(value)
            if normalized:
                if kind == "folder":
                    folders.append(normalized)
                else:
                    paths.append(normalized)
        return " "

    cleaned_query = FILTER_PATTERN.sub(replace, raw_query)
    cleaned_query = " ".join(cleaned_query.split())
    return QueryFilters(
        cleaned_query=cleaned_query,
        folders=tuple(_dedupe(folders)),
        paths=tuple(_dedupe(paths)),
        tags=tuple(_dedupe(tags)),
    )


def chunk_matches_filters(chunk: RagChunk, filters: QueryFilters) -> bool:
    chunk_path = chunk.path.lower()
    chunk_directory = chunk.directory.lower()
    chunk_tags = {tag.lower() for tag in chunk.tags}

    if filters.folders and not any(
        chunk_directory == folder or chunk_directory.startswith(f"{folder}/")
        for folder in filters.folders
    ):
        return False

    if filters.paths and not any(path in chunk_path for path in filters.paths):
        return False

    if filters.tags and not all(tag in chunk_tags for tag in filters.tags):
        return False

    return True


def _dedupe(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique

