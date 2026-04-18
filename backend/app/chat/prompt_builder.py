from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..chat.types import ChatMessagePayload
from ..memory.types import MemoryPromptPayload
from ..retrieval.types import PromptContextPayload
from ..storage.models import Message
from ..tools import ToolContextPlan
from .strategy import ContextStrategy
from .token_budget import estimate_text_tokens, truncate_text_to_token_budget

SectionKind = Literal["summary", "history", "memory", "retrieval"]

SUMMARY_SYSTEM_PROMPT = (
    "Earlier turns were compacted into the following conversation recap. "
    "Treat it as a lossy summary of older context and defer to the recent turns if there is any conflict."
)


@dataclass(frozen=True)
class HistoryWindow:
    older_messages: list[Message]
    recent_messages: list[Message]


@dataclass(frozen=True)
class PromptSection:
    kind: SectionKind
    title: str
    body: str
    item_count: int

    def to_payload(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "title": self.title,
            "body": self.body,
            "item_count": self.item_count,
        }


@dataclass(frozen=True)
class PromptComposition:
    prefix_messages: list[ChatMessagePayload]
    inspection: dict[str, object]


def build_prompt_composition(
    *,
    query: str,
    history_window: HistoryWindow,
    strategy: ContextStrategy,
    memory_prompt: MemoryPromptPayload,
    tool_plan: ToolContextPlan,
    retrieval_payload: PromptContextPayload,
) -> PromptComposition:
    sections: list[PromptSection] = []
    prefix_messages: list[ChatMessagePayload] = []
    recent_turn_count = count_turns(history_window.recent_messages)
    older_turn_count = count_turns(history_window.older_messages)

    summary_text = summarize_older_history(
        messages=history_window.older_messages,
        token_budget=strategy.summary_token_budget,
    )
    if summary_text:
        prefix_messages.append(
            ChatMessagePayload(
                role="system",
                content=f"{SUMMARY_SYSTEM_PROMPT}\n\nConversation recap:\n{summary_text}",
            )
        )

    if memory_prompt.messages:
        prefix_messages.extend(memory_prompt.messages)

    retrieval_sources = retrieval_payload.sources
    if retrieval_payload.context_message is not None:
        prefix_messages.append(retrieval_payload.context_message)

    inspection_summary = build_context_inspection_summary(
        history_window=history_window,
        older_summary=summary_text,
        memory_prompt=memory_prompt,
        retrieval_payload=retrieval_payload,
    )
    if inspection_summary:
        sections.append(
            PromptSection(
                kind="summary",
                title="上下文摘要",
                body=inspection_summary,
                item_count=recent_turn_count,
            )
        )

    inspection = {
        "query": query,
        "strategy": strategy.name,
        "tool_mode": tool_plan.mode,
        "tool_plan": list(tool_plan.requested_tools),
        "older_message_count": older_turn_count,
        "recent_message_count": recent_turn_count,
        "memory_count": int(
            (memory_prompt.debug.get("memory_documents", 0) or 0)
            + (memory_prompt.debug.get("memory_hits", 0) or 0)
        ),
        "source_count": len(retrieval_sources),
        "sections": [section.to_payload() for section in sections],
    }
    return PromptComposition(prefix_messages=prefix_messages, inspection=inspection)


def count_turns(messages: list[Message]) -> int:
    count = 0
    expecting_user = True
    for message in messages:
        if message.role == "user" and expecting_user:
            count += 1
            expecting_user = False
            continue
        if message.role == "assistant":
            expecting_user = True
    return count or (1 if messages else 0)


def summarize_older_history(*, messages: list[Message], token_budget: int) -> str:
    if not messages:
        return ""

    max_tokens = max(96, token_budget)
    lines: list[str] = []
    used_tokens = 0
    turn_index = 0
    pending_user: Message | None = None

    for message in messages:
        if message.role == "user":
            pending_user = message
            continue

        if message.role != "assistant":
            continue

        turn_index += 1
        lines_for_turn = render_turn_lines(turn_index=turn_index, user_message=pending_user, assistant_message=message)
        if not lines_for_turn:
            pending_user = None
            continue

        block = "\n".join(lines_for_turn)
        block_tokens = estimate_text_tokens(block)
        next_tokens = used_tokens + block_tokens
        if lines and next_tokens > max_tokens:
            break
        if not lines and block_tokens > max_tokens:
            block = truncate_text_to_token_budget(block, token_budget=max_tokens)
            lines.append(block)
            break

        lines.append(block)
        used_tokens = next_tokens
        pending_user = None

    if pending_user is not None:
        next_block = "\n".join(render_turn_lines(turn_index=turn_index + 1, user_message=pending_user, assistant_message=None))
        if next_block:
            remaining_tokens = max_tokens - used_tokens
            if remaining_tokens > 8:
                if estimate_text_tokens(next_block) > remaining_tokens:
                    next_block = truncate_text_to_token_budget(next_block, token_budget=remaining_tokens)
                lines.append(next_block)

    return "\n\n".join(lines)


def render_turn_lines(
    *,
    turn_index: int,
    user_message: Message | None,
    assistant_message: Message | None,
) -> list[str]:
    lines = [f"Turn {turn_index}"]
    user_text = summarize_message_content(user_message)
    assistant_text = summarize_message_content(assistant_message)

    if user_text:
        lines.append(f"User: {user_text}")
    if assistant_text:
        lines.append(f"Assistant: {assistant_text}")
    return lines if len(lines) > 1 else []


def summarize_message_content(message: Message | None) -> str:
    if message is None:
        return ""

    parts: list[str] = []
    content = compact_text(message.content, token_limit=72)
    if content:
        parts.append(content)

    if message.attachments:
        names = ", ".join(attachment.original_name for attachment in message.attachments[:3])
        suffix = "" if len(message.attachments) <= 3 else ", …"
        parts.append(f"attachments: {names}{suffix}")

    return " | ".join(parts)


def compact_text(value: str, *, token_limit: int) -> str:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return ""
    if estimate_text_tokens(normalized) <= token_limit:
        return normalized
    return truncate_text_to_token_budget(normalized, token_budget=token_limit)


def render_recent_history(messages: list[Message]) -> str:
    lines: list[str] = []
    for message in messages:
        role = "User" if message.role == "user" else "Assistant"
        summary = summarize_message_content(message)
        if summary:
            lines.append(f"{role}: {summary}")
    return "\n".join(lines)


def build_context_inspection_summary(
    *,
    history_window: HistoryWindow,
    older_summary: str,
    memory_prompt: MemoryPromptPayload,
    retrieval_payload: PromptContextPayload,
) -> str:
    recent_turn_count = count_turns(history_window.recent_messages)
    older_turn_count = count_turns(history_window.older_messages)
    recent_user_points = recent_user_focus_points(history_window.recent_messages)
    has_attachments = any(message.role == "user" and message.attachments for message in history_window.recent_messages)
    memory_count = int(
        (memory_prompt.debug.get("memory_documents", 0) or 0)
        + (memory_prompt.debug.get("memory_hits", 0) or 0)
    )
    source_count = len(retrieval_payload.sources)

    sentences: list[str] = []
    if recent_turn_count > 0:
        sentences.append(f"本次回答截取了最近{recent_turn_count}轮对话。")
    if older_turn_count > 0:
        sentences.append(f"更早的{older_turn_count}轮内容已压缩。")
    if recent_user_points:
        sentences.append(f"最近主要围绕这些内容继续交流：{recent_user_points}。")
    if memory_count > 0:
        sentences.append(f"另外参考了{memory_count}条记忆信息。")
    if source_count > 0:
        sentences.append(f"另外参考了{source_count}条外部资料。")
    if not sentences and older_summary:
        sentences.append(f"上下文摘要：{compact_text(older_summary, token_limit=96)}")
    return " ".join(sentences).strip()


def recent_user_focus_points(messages: list[Message]) -> str:
    points: list[str] = []
    for message in messages:
        if message.role != "user":
            continue
        summary = summarize_message_content(message)
        if not summary:
            continue
        normalized = compact_text(summary, token_limit=28)
        if normalized and normalized not in points:
            points.append(normalized)
    if not points:
        return ""
    return "；".join(points[-3:])


def render_retrieval_sources(sources: list[dict[str, object]]) -> str:
    if not sources:
        return "No external sources were injected."

    lines: list[str] = []
    for index, source in enumerate(sources, start=1):
        source_type = str(source.get("type", "note")).strip() or "note"
        label = str(
            source.get("title")
            or source.get("path")
            or source.get("url")
            or source.get("domain")
            or f"Source {index}"
        ).strip()
        excerpt = compact_text(str(source.get("excerpt", "")).strip(), token_limit=72)
        line = f"{index}. [{source_type}] {label}"
        if excerpt:
            line += f" :: {excerpt}"
        lines.append(line)
    return "\n".join(lines)
