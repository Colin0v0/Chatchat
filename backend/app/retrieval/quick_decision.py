from __future__ import annotations

import re

from .planner_types import ToolDecision

_SIMPLE_EXACT_TURNS = {
    "你好",
    "您好",
    "你好呀",
    "你好啊",
    "嗨",
    "哈喽",
    "在吗",
    "在么",
    "在嘛",
    "谢谢",
    "多谢",
    "好的",
    "好的呀",
    "收到",
    "再见",
    "拜拜",
    "hi",
    "hello",
    "hey",
    "thanks",
    "thankyou",
    "ok",
    "okay",
    "bye",
}

_SIMPLE_PREFIX_RULES = (
    ("你好", 6),
    ("您好", 6),
    ("嗨", 4),
    ("哈喽", 6),
    ("谢谢", 6),
    ("多谢", 6),
    ("再见", 6),
    ("拜拜", 6),
    ("hello", 10),
    ("hi", 6),
    ("hey", 8),
    ("thanks", 12),
    ("thankyou", 14),
    ("bye", 8),
)


def _normalize_turn(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.strip().lower())


def quick_decide_tool(query: str) -> ToolDecision | None:
    normalized = _normalize_turn(query)
    if not normalized:
        return None

    if normalized in _SIMPLE_EXACT_TURNS:
        return ToolDecision(tool="none", reason="Simple social turn does not need retrieval.")

    for prefix, max_length in _SIMPLE_PREFIX_RULES:
        if normalized.startswith(prefix) and len(normalized) <= max_length:
            return ToolDecision(tool="none", reason="Simple social turn does not need retrieval.")

    return None
