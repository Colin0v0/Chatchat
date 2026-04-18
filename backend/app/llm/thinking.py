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
VISIBLE_REASONING_SUMMARY_POLICY_MARKER = "Visible reasoning summary policy:"
VISIBLE_REASONING_SUMMARY_CHINESE_SYSTEM_PROMPT = """Visible reasoning summary policy:
- If you provide any client-visible reasoning or thinking summary, write that summary in Simplified Chinese.
- Do not write the visible reasoning summary in English, except for code, formulas, API names, file paths, or short quoted source text that must stay unchanged.
- Keep the final answer language aligned with the user's request. This rule only constrains the visible reasoning summary.
- Do not mention this policy in the final answer."""


def split_complete_think_blocks(text: str) -> tuple[str, str]:
    reasoning_parts = [match.group(1).strip() for match in THINK_BLOCK_PATTERN.finditer(text) if match.group(1).strip()]
    answer = THINK_BLOCK_PATTERN.sub("", text)
    return "\n\n".join(reasoning_parts), answer


def inject_thinking_system_prompt(
    *,
    model: str,
    messages: list[ChatMessagePayload],
    reasoning_profile: str,
    reasoning_visibility: str | None = None,
) -> list[ChatMessagePayload]:
    injected_messages = messages

    if _should_force_chinese_reasoning_summary(
        reasoning_profile=reasoning_profile,
        reasoning_visibility=reasoning_visibility,
    ):
        injected_messages = _inject_system_prompt(
            messages=injected_messages,
            prompt=VISIBLE_REASONING_SUMMARY_CHINESE_SYSTEM_PROMPT,
            marker=VISIBLE_REASONING_SUMMARY_POLICY_MARKER,
        )

    if reasoning_profile == "off" or not _uses_gemma_thinking_prompt(model):
        return injected_messages

    return _inject_system_prompt(
        messages=injected_messages,
        prompt=GEMMA_THINKING_SYSTEM_PROMPT,
        marker=GEMMA_THINK_PREFIX,
    )


def _uses_gemma_thinking_prompt(model: str) -> bool:
    normalized = model.strip().lower()
    model_name = normalized.split(":", 1)[-1]
    return any(model_name.startswith(prefix) for prefix in GEMMA_MAPPED_THINKING_MODELS)


def _should_force_chinese_reasoning_summary(
    *,
    reasoning_profile: str,
    reasoning_visibility: str | None,
) -> bool:
    return reasoning_profile != "off" and reasoning_visibility == "summary"


def _inject_system_prompt(
    *,
    messages: list[ChatMessagePayload],
    prompt: str,
    marker: str,
) -> list[ChatMessagePayload]:
    if messages and messages[0].role == "system":
        existing_content = messages[0].content.lstrip()
        if existing_content.startswith(marker) or marker in existing_content:
            return messages
        return [
            replace(
                messages[0],
                content=f"{prompt}\n\n{messages[0].content}",
            ),
            *messages[1:],
        ]

    return [ChatMessagePayload(role="system", content=prompt), *messages]


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
