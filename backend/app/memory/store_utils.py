from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from ..storage.models import MemoryItem
from .types import MemoryDocumentType

TOKEN_PATTERN = re.compile(r"[0-9A-Za-z_\u4e00-\u9fff]{2,}")
PURE_CJK_PATTERN = re.compile(r"^[\u4e00-\u9fff]+$")
MEMORY_STOPWORDS = {
    "the",
    "and",
    "user",
    "assistant",
    "memory",
    "context",
    "用户",
    "助手",
    "记忆",
    "上下文",
}

DOCUMENT_TITLES: dict[MemoryDocumentType, str] = {
    "user_profile": "User Profile",
    "workspace_profile": "Workspace Context",
    "conversation_brief": "Conversation Brief",
}

KIND_LABELS = {
    "profile": "Profile",
    "preference": "Preference",
    "goal": "Goal",
    "project": "Project",
    "fact": "Fact",
    "constraint": "Constraint",
}
PROMOTE_EVIDENCE_THRESHOLD = 2
PROMOTABLE_KINDS = {"profile", "preference"}
INJECTABLE_CONFIDENCE_STATES = {"inferred", "confirmed"}
SHORT_STYLE_MARKERS = {"短", "简短", "简洁", "简明", "直接", "短一点", "少废话", "concise", "brief", "short"}
DETAILED_STYLE_MARKERS = {"详细", "展开", "完整", "深入", "细致", "长一点", "解释充分", "detailed", "verbose"}
CONFLICT_SUBJECT_MARKERS = {
    "姓名",
    "名字",
    "生日",
    "邮箱",
    "电话",
    "住址",
    "地址",
    "城市",
    "职业",
    "公司",
    "语言",
    "称呼",
    "name",
    "birthday",
    "email",
    "phone",
    "address",
    "city",
    "job",
    "company",
    "language",
    "nickname",
}


@dataclass(frozen=True)
class MemoryCollection:
    global_items: list[MemoryItem]
    conversation_items: list[MemoryItem]


def utcnow() -> datetime:
    # 中文注释：统一返回带 UTC 时区的时间，避免和数据库里的 aware datetime 混用时报错。
    return datetime.now(timezone.utc)


def normalize_tags(tags: list[str] | tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    for item in tags:
        value = str(item).strip()
        if value and value not in normalized:
            normalized.append(value)
    return normalized[:6]


def normalize_memory_text(value: str, *, max_length: int) -> str:
    compact = " ".join(value.strip().split())
    return compact[:max_length].strip()


def normalize_memory_key(value: str) -> str:
    return normalize_memory_text(value, max_length=255).casefold()


def serialize_evidence(
    *,
    user_message_id: int | None,
    assistant_message_id: int | None,
    existing: list[dict[str, object]] | None = None,
) -> str:
    evidence = list(existing or [])
    if user_message_id is not None or assistant_message_id is not None:
        next_item = {
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
            "observed_at": utcnow().isoformat(),
        }
        signature = (user_message_id, assistant_message_id)
        seen = {
            (item.get("user_message_id"), item.get("assistant_message_id"))
            for item in evidence
            if isinstance(item, dict)
        }
        if signature not in seen:
            evidence.append(next_item)
    return json.dumps(evidence[-12:], ensure_ascii=False)


def memory_token_set(*parts: str) -> set[str]:
    tokens: set[str] = set()
    for part in parts:
        for token in TOKEN_PATTERN.findall(part.casefold()):
            normalized = token.strip()
            if len(normalized) < 2 or normalized in MEMORY_STOPWORDS:
                continue
            tokens.add(normalized)
            if PURE_CJK_PATTERN.fullmatch(normalized):
                tokens.update(_cjk_ngrams(normalized))
    return tokens


def _cjk_ngrams(value: str) -> set[str]:
    grams: set[str] = set()
    for size in (2, 3):
        if len(value) < size:
            continue
        for index in range(len(value) - size + 1):
            grams.add(value[index : index + size])
    return grams


def memory_similarity(
    *,
    left_title: str,
    left_detail: str,
    right_title: str,
    right_detail: str,
) -> float:
    left_text = normalize_memory_key(" ".join([left_title, left_detail]).strip())
    right_text = normalize_memory_key(" ".join([right_title, right_detail]).strip())
    if left_text and left_text == right_text:
        return 1.0

    left_tokens = memory_token_set(left_title, left_detail)
    right_tokens = memory_token_set(right_title, right_detail)
    if not left_tokens or not right_tokens:
        return 0.0
    intersection = left_tokens & right_tokens
    if not intersection:
        return 0.0
    union = left_tokens | right_tokens
    return max(len(intersection) / len(union), len(intersection) / min(len(left_tokens), len(right_tokens)))
