from __future__ import annotations

import math
import re

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]|[^\s]")


def estimate_text_tokens(value: str) -> int:
    normalized = value.strip()
    if not normalized:
        return 0

    total = 0
    for token in TOKEN_PATTERN.findall(normalized):
        if not token:
            continue
        if len(token) == 1 and "\u4e00" <= token <= "\u9fff":
            total += 1
            continue
        if token.isascii() and any(character.isalnum() for character in token):
            total += max(1, math.ceil(len(token) / 4))
            continue
        total += 1
    return total


def truncate_text_to_token_budget(value: str, *, token_budget: int) -> str:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return ""

    max_tokens = max(1, token_budget)
    current_tokens = 0
    cutoff = len(normalized)
    matched = False

    for match in TOKEN_PATTERN.finditer(normalized):
        matched = True
        token = match.group(0)
        token_cost = estimate_text_tokens(token)
        if current_tokens > 0 and current_tokens + token_cost > max_tokens:
            cutoff = match.start()
            break
        if current_tokens == 0 and token_cost > max_tokens:
            return token
        current_tokens += token_cost

    if not matched:
        return normalized

    compact = normalized[:cutoff].rstrip()
    if compact == normalized:
        return compact
    return compact.rstrip() + "…"
