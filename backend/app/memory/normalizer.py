from __future__ import annotations

import re
from dataclasses import dataclass

from .types import MemoryCandidate, MemoryKind

WHITESPACE_PATTERN = re.compile(r"\s+")
HAS_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F900-\U0001F9FF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "]+",
    flags=re.UNICODE,
)

DROP_PATTERNS = (
    "assistant capabilities",
    "assistant can:",
    "flexible interaction",
    "user accepts knowledge q&a",
    "alongside structured tasks",
)

TAG_MAP = {
    "personal": "个人",
    "profile": "个人",
    "name": "姓名",
    "language": "语言",
    "preference": "偏好",
    "capabilities": "能力",
    "analysis": "分析",
    "processing": "处理",
    "chat": "聊天",
    "q&a": "问答",
    "qa": "问答",
    "flexibility": "灵活交流",
}

NAME_PATTERNS = (
    re.compile(r"(?:user(?:'s)? name is|name is|named|called)\s+(.+?)(?:[.,;]|$)", re.IGNORECASE),
    re.compile(r"(?:用户叫|名字是|姓名是)\s*(.+?)(?:[，。；]|$)"),
)

BIRTHDAY_PATTERNS = (
    re.compile(r"(?:birthday is|date of birth is|born on)\s+(.+?)(?:[.,;]|$)", re.IGNORECASE),
    re.compile(r"(?:生日是|出生日期是)\s*(.+?)(?:[，。；]|$)"),
)

LANGUAGE_PATTERNS = (
    re.compile(r"(?:respond in|reply in|use)\s+(chinese|english|中文|英文)", re.IGNORECASE),
    re.compile(r"(?:preferred language|response language)\s*(?:is|:)\s*(chinese|english|中文|英文)", re.IGNORECASE),
)


@dataclass(frozen=True)
class NormalizedMemory:
    kind: MemoryKind
    title: str
    detail: str
    tags: tuple[str, ...]


def normalize_candidate(candidate: MemoryCandidate) -> MemoryCandidate | None:
    normalized = normalize_memory_fields(
        kind=candidate.kind,
        title=candidate.title,
        detail=candidate.detail,
        tags=candidate.tags,
    )
    if normalized is None:
        return None

    return MemoryCandidate(
        scope=candidate.scope,
        kind=normalized.kind,
        title=normalized.title,
        detail=normalized.detail,
        tags=normalized.tags,
        confidence=candidate.confidence,
    )


def normalize_memory_fields(
    *,
    kind: MemoryKind,
    title: str,
    detail: str,
    tags: tuple[str, ...] | list[str],
) -> NormalizedMemory | None:
    clean_title = sanitize_text(title, max_length=255)
    clean_detail = sanitize_text(detail, max_length=4000)
    combined = " ".join(part for part in [clean_title, clean_detail] if part).casefold()
    if any(pattern in combined for pattern in DROP_PATTERNS):
        return None

    translated_tags = normalize_tags(tags)
    name = extract_name(clean_title, clean_detail)
    if name:
        return NormalizedMemory(
            kind="profile",
            title="姓名",
            detail=f"用户叫{name}",
            tags=merge_tags(("个人", "姓名"), translated_tags),
        )

    if clean_title in {"姓名", "名字"} and clean_detail:
        # 有些模型会把姓名拆成 title=姓名、detail=名字本身，这里收束成统一画像格式。
        normalized_name = clean_detail.removeprefix("用户叫").strip()
        return NormalizedMemory(
            kind="profile",
            title="姓名",
            detail=f"用户叫{normalized_name}",
            tags=merge_tags(("个人", "姓名"), translated_tags),
        )

    birthday = extract_birthday(clean_title, clean_detail)
    if birthday:
        return NormalizedMemory(
            kind="profile",
            title="生日",
            detail=f"用户生日是{birthday}",
            tags=merge_tags(("个人", "生日"), translated_tags),
        )

    if clean_title in {"生日", "出生日期"} and clean_detail:
        # 生日属于稳定身份资料，统一成可直接进入全局画像的短句。
        normalized_birthday = clean_detail.removeprefix("用户生日是").strip()
        return NormalizedMemory(
            kind="profile",
            title="生日",
            detail=f"用户生日是{normalized_birthday}",
            tags=merge_tags(("个人", "生日"), translated_tags),
        )

    language = extract_language(clean_title, clean_detail)
    if language:
        return NormalizedMemory(
            kind="preference",
            title="回复语言",
            detail=f"默认使用{language}回复。",
            tags=merge_tags(("语言", "偏好"), translated_tags),
        )

    title_map = {
        "user name": ("profile", "姓名"),
        "name": ("profile", "姓名"),
        "preferred language": ("preference", "回复语言"),
        "response language": ("preference", "回复语言"),
        "language preference": ("preference", "回复语言"),
        "birthday": ("profile", "生日"),
        "date of birth": ("profile", "生日"),
    }
    lowered_title = clean_title.casefold()
    mapped = title_map.get(lowered_title)
    if mapped is not None:
        mapped_kind, mapped_title = mapped
        clean_title = mapped_title
        kind = mapped_kind

    if clean_detail and not HAS_CJK_PATTERN.search(clean_detail):
        clean_detail = translate_known_detail(clean_detail)
    if clean_title and not HAS_CJK_PATTERN.search(clean_title):
        clean_title = translate_known_title(clean_title) or clean_title

    if not clean_title:
        return None

    return NormalizedMemory(
        kind=kind,
        title=clean_title,
        detail=clean_detail,
        tags=translated_tags,
    )


def sanitize_text(value: str, *, max_length: int) -> str:
    collapsed = WHITESPACE_PATTERN.sub(" ", value.strip())
    without_emoji = EMOJI_PATTERN.sub("", collapsed)
    normalized = without_emoji.replace("(", "（").replace(")", "）")
    return normalized[:max_length].strip(" -:;,，。")


def normalize_tags(tags: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for tag in tags:
        value = sanitize_text(str(tag), max_length=24).casefold()
        if not value:
            continue
        translated = TAG_MAP.get(value, sanitize_text(str(tag), max_length=24))
        if translated and translated not in normalized:
            normalized.append(translated)
    return tuple(normalized[:6])


def merge_tags(primary: tuple[str, ...], secondary: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for tag in [*primary, *secondary]:
        if tag and tag not in merged:
            merged.append(tag)
    return tuple(merged[:6])


def extract_name(title: str, detail: str) -> str | None:
    for text in [detail, title]:
        for pattern in NAME_PATTERNS:
            match = pattern.search(text)
            if match is None:
                continue
            raw = sanitize_text(match.group(1), max_length=80)
            if not raw:
                continue
            raw = raw.removeprefix("用户").strip()
            if raw:
                return raw
    return None


def extract_birthday(title: str, detail: str) -> str | None:
    for text in [detail, title]:
        for pattern in BIRTHDAY_PATTERNS:
            match = pattern.search(text)
            if match is None:
                continue
            raw = sanitize_text(match.group(1), max_length=80)
            if raw:
                return raw
    return None


def extract_language(title: str, detail: str) -> str | None:
    for text in [detail, title]:
        for pattern in LANGUAGE_PATTERNS:
            match = pattern.search(text)
            if match is None:
                continue
            value = match.group(1).strip().casefold()
            if value in {"chinese", "中文"}:
                return "中文"
            if value in {"english", "英文"}:
                return "英文"
    return None


def translate_known_title(value: str) -> str | None:
    lowered = value.casefold()
    mapping = {
        "user name": "姓名",
        "name": "姓名",
        "preferred language": "回复语言",
        "response language": "回复语言",
        "language preference": "回复语言",
        "birthday": "生日",
        "date of birth": "生日",
    }
    return mapping.get(lowered)


def translate_known_detail(value: str) -> str:
    lowered = value.casefold()
    if lowered.startswith("user prefers chinese"):
        return "默认使用中文回复。"
    if lowered.startswith("user prefers english"):
        return "默认使用英文回复。"
    return value
