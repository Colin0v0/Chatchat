from __future__ import annotations

from ..chat.types import ChatMessagePayload
from ..chat.token_budget import truncate_text_to_token_budget
from ..runtime.model_runner import complete_model_response

SUMMARY_SYSTEM_PROMPT = """Summarize one past chat turn for future semantic recall.
Return 1-2 concise Simplified Chinese sentences.
Keep durable entities, decisions, user preferences, tasks, repo names, errors, dates, and constraints.
Do not invent facts. Do not mention that this is a summary.
"""

DYNAMIC_RECAP_SYSTEM_PROMPT = """You turn retrieved past-chat snippets into a compact private context note.
Use Simplified Chinese.
Only include details that could help answer the current user request.
Do not save anything as memory. Do not invent facts.
Return at most 5 bullets.
"""


class PastChatSummarizer:
    def __init__(self, *, model: str):
        self._model = model.strip()

    async def summarize_turn(
        self,
        *,
        conversation_title: str,
        user_message: str,
        assistant_message: str,
    ) -> str:
        if not self._model:
            return ""
        content = "\n\n".join(
            [
                f"Conversation title: {conversation_title.strip() or 'Untitled'}",
                f"User: {user_message.strip()}",
                f"Assistant: {assistant_message.strip()}",
            ]
        )
        summary = await complete_model_response(
            model=self._model,
            requested_reasoning=False,
            messages=[
                ChatMessagePayload(role="system", content=SUMMARY_SYSTEM_PROMPT),
                ChatMessagePayload(role="user", content=content),
            ],
        )
        return _normalize_summary(summary)

    async def synthesize_dynamic_recap(
        self,
        *,
        query: str,
        snippets: list[str],
    ) -> str:
        if not snippets or not self._model:
            return ""
        content = "\n\n".join(
            [
                f"Current user request: {query.strip()}",
                "Past-chat snippets:",
                "\n".join(f"- {snippet}" for snippet in snippets[:8]),
            ]
        )
        summary = await complete_model_response(
            model=self._model,
            requested_reasoning=False,
            messages=[
                ChatMessagePayload(role="system", content=DYNAMIC_RECAP_SYSTEM_PROMPT),
                ChatMessagePayload(role="user", content=content),
            ],
        )
        return _normalize_summary(summary)


def _normalize_summary(value: str) -> str:
    text = "\n".join(line.strip().strip("`") for line in value.splitlines() if line.strip())
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    return truncate_text_to_token_budget(text, token_budget=180).strip()


def build_turn_index_text(*, conversation_title: str, user_message: str, assistant_message: str) -> str:
    # 中文注释：这不是摘要，只是给历史检索和向量索引用的原始 turn 文本。
    content = "\n\n".join(
        part.strip()
        for part in (
            conversation_title,
            f"User: {user_message}",
            f"Assistant: {assistant_message}",
        )
        if part and part.strip()
    )
    return truncate_text_to_token_budget(content, token_budget=360).strip()
