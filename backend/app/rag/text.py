from __future__ import annotations

import re

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")


def tokenize_text(text: str) -> list[str]:
    return [item.lower() for item in TOKEN_PATTERN.findall(text)]


def normalize_tag(tag: str) -> str:
    normalized = tag.strip().strip("'\"").lstrip("#").strip().lower()
    return normalized


def normalize_path_fragment(value: str) -> str:
    return value.strip().strip("'\"").replace("\\", "/").strip("/").lower()

