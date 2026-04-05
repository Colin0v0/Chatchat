from __future__ import annotations

import re

FILTER_PATTERN = re.compile(r"\b(?:folder|tag|path):\S+", re.IGNORECASE)
SPACE_PATTERN = re.compile(r"\s+")
TRAILING_PUNCTUATION = " ,.;:!?，。；：！？-_"


def generate_conversation_title(
    *,
    content: str,
    uploaded_count: int,
    max_length: int,
) -> str:
    normalized = SPACE_PATTERN.sub(" ", FILTER_PATTERN.sub("", content)).strip()
    if normalized:
        primary = split_primary_clause(normalized).strip(TRAILING_PUNCTUATION)
        if primary:
            return truncate_title(primary, max_length=max_length)

    if uploaded_count:
        return "Attachment Analysis" if uploaded_count == 1 else f"{uploaded_count} Attachments"
    return "New chat"


def should_refresh_title(*, current_title: str, source_content: str, uploaded_count: int, max_length: int) -> bool:
    expected_initial = generate_conversation_title(
        content=source_content,
        uploaded_count=uploaded_count,
        max_length=max_length,
    )
    normalized_current = current_title.strip()
    return normalized_current in {"New chat", "Attachment chat", "Attachment Analysis", expected_initial}


def split_primary_clause(value: str) -> str:
    for separator in ("\n", "。", "！", "？", ".", "!", "?", "，", ",", " - ", " | "):
        if separator in value:
            head = value.split(separator, 1)[0].strip()
            if len(head) >= 4:
                return head
    return value


def truncate_title(value: str, *, max_length: int) -> str:
    text = value.strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip(TRAILING_PUNCTUATION) + "…"
