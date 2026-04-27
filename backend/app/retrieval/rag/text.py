from __future__ import annotations

import re

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")


def tokenize_text(text: str) -> list[str]:
    tokens: list[str] = []
    for item in TOKEN_PATTERN.findall(text):
        normalized = item.lower()
        if not normalized:
            continue
        if _is_cjk_token(normalized):
            tokens.extend(_tokenize_cjk(normalized))
            continue
        tokens.append(normalized)
    return tokens


def _is_cjk_token(value: str) -> bool:
    return bool(value) and all("\u4e00" <= char <= "\u9fff" for char in value)


def _tokenize_cjk(value: str) -> list[str]:
    if len(value) <= 1:
        return [value]

    tokens = [value]
    for index in range(len(value)):
        tokens.append(value[index])
        if index + 1 < len(value):
            tokens.append(value[index : index + 2])

    unique_tokens: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token and token not in seen:
            seen.add(token)
            unique_tokens.append(token)
    return unique_tokens


def normalize_tag(tag: str) -> str:
    normalized = tag.strip().strip("'\"").lstrip("#").strip().lower()
    return normalized


def normalize_path_fragment(value: str) -> str:
    return value.strip().strip("'\"").replace("\\", "/").strip("/").lower()
