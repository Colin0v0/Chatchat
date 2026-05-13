from __future__ import annotations

import re

from .types import MemoryCandidate

EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
TOKEN_PATTERN = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|[A-Za-z0-9_-]{32,})\b")
ID_PATTERN = re.compile(r"(身份证|护照|银行卡|信用卡|社保|住址|地址|password|密码|api key|secret)", re.IGNORECASE)
PASSWORD_PATTERN = re.compile(r"(?:密码|password|passcode|token|secret|api key)\s*[:：=]\s*\S+", re.IGNORECASE)


def is_sensitive_text(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    return bool(
        EMAIL_PATTERN.search(text)
        or PHONE_PATTERN.search(text)
        or TOKEN_PATTERN.search(text)
        or ID_PATTERN.search(text)
        or PASSWORD_PATTERN.search(text)
    )


def candidate_is_sensitive(candidate: MemoryCandidate) -> bool:
    # 中文注释：敏感信息默认不进入候选记忆；用户明确打开 sensitive_memory_enabled 后才允许。
    content = " ".join([candidate.title, candidate.detail, " ".join(candidate.tags)])
    return is_sensitive_text(content)


def filter_sensitive_candidates(
    *,
    candidates: list[MemoryCandidate],
    allow_sensitive: bool,
) -> tuple[list[MemoryCandidate], int]:
    if allow_sensitive:
        return candidates, 0
    kept: list[MemoryCandidate] = []
    skipped = 0
    for candidate in candidates:
        if candidate_is_sensitive(candidate):
            skipped += 1
            continue
        kept.append(candidate)
    return kept, skipped
