from __future__ import annotations

import re
from dataclasses import replace

from ..chat.types import ChatMessagePayload


THINK_BLOCK_PATTERN = re.compile(r"<think>(.*?)</think>", flags=re.IGNORECASE | re.DOTALL)
GEMMA_THINK_PREFIX = "<|think|>"
GEMMA_MAPPED_THINKING_MODELS = ("claude-sonnet-",)
GEMMA_THINKING_SYSTEM_PROMPT = """<|think|>
Thinking is enabled for this conversation.
First write your internal reasoning inside a single <think>...</think> block.
Then write the final answer outside the think block.
Do not mention these formatting instructions in the final answer."""


def split_complete_think_blocks(text: str) -> tuple[str, str]:
    reasoning_parts = [match.group(1).strip() for match in THINK_BLOCK_PATTERN.finditer(text) if match.group(1).strip()]
    answer = THINK_BLOCK_PATTERN.sub("", text)
    return "\n\n".join(reasoning_parts), answer


def inject_thinking_system_prompt(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    reasoning_profile: str,
) -> list[ChatMessagePayload]:
    if reasoning_profile == "off" or not _uses_gemma_thinking_prompt(model):
        return messages

    if messages and messages[0].role == "system":
        existing_content = messages[0].content.lstrip()
        if existing_content.startswith(GEMMA_THINK_PREFIX):
            return messages
        return [
            replace(
                messages[0],
                content=f"{GEMMA_THINKING_SYSTEM_PROMPT}\n\n{messages[0].content}",
            ),
            *messages[1:],
        ]

    return [ChatMessagePayload(role="system", content=GEMMA_THINKING_SYSTEM_PROMPT), *messages]


def _uses_gemma_thinking_prompt(model: str) -> bool:
    normalized = model.strip().lower()
    model_name = normalized.split(":", 1)[-1]
    return any(model_name.startswith(prefix) for prefix in GEMMA_MAPPED_THINKING_MODELS)


class ThinkTagStreamNormalizer:
    def __init__(self, *, emit_reasoning: bool) -> None:
        self._emit_reasoning = emit_reasoning
        self._in_think = False
        self._carry = ""
        self._open_tag = "<think>"
        self._close_tag = "</think>"

    def _suffix_len_matching_prefix(self, text: str, prefix: str) -> int:
        max_len = min(len(text), len(prefix) - 1)
        for size in range(max_len, 0, -1):
            if text.endswith(prefix[:size]):
                return size
        return 0

    def feed(self, chunk: str) -> tuple[str, str]:
        data = self._carry + chunk
        self._carry = ""
        reasoning: list[str] = []
        answer: list[str] = []
        i = 0

        while i < len(data):
            if self._in_think:
                close_at = data.find(self._close_tag, i)
                if close_at == -1:
                    tail = data[i:]
                    keep = self._suffix_len_matching_prefix(tail, self._close_tag)
                    visible = tail[:-keep] if keep else tail
                    if self._emit_reasoning:
                        reasoning.append(visible)
                    self._carry = tail[-keep:] if keep else ""
                    return "".join(reasoning), "".join(answer)

                if self._emit_reasoning:
                    reasoning.append(data[i:close_at])
                i = close_at + len(self._close_tag)
                self._in_think = False
                continue

            open_at = data.find(self._open_tag, i)
            if open_at == -1:
                tail = data[i:]
                keep = self._suffix_len_matching_prefix(tail, self._open_tag)
                answer.append(tail[:-keep] if keep else tail)
                self._carry = tail[-keep:] if keep else ""
                return "".join(reasoning), "".join(answer)

            answer.append(data[i:open_at])
            i = open_at + len(self._open_tag)
            self._in_think = True

        return "".join(reasoning), "".join(answer)

    def flush(self) -> tuple[str, str]:
        if not self._carry:
            return "", ""

        tail = self._carry
        self._carry = ""
        if self._in_think:
            return (tail if self._emit_reasoning else ""), ""
        return "", tail
