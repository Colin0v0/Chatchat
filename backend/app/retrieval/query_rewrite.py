from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

from ..chat.types import ChatMessagePayload
from ..core.config import Settings
from ..runtime.model_runner import complete_model_response

REWRITE_SYSTEM_PROMPT = """You rewrite the latest user request into a standalone retrieval query for searching a private Markdown knowledge base.
Preserve the user's intent, entities, filenames, dates, version numbers, error messages, APIs, and code symbols.
Resolve references such as it, that, this plan, 这个, 那个, 上面那个 using the recent conversation when needed.
Keep the user's original language unless a technical term or name should remain in English.
Return exactly one standalone retrieval query on a single line.
Do not explain anything.
"""
INVALID_PREFIX_PATTERN = re.compile(r"^(query|rewrite|rewritten query|search query)\s*:\s*", re.IGNORECASE)
INVALID_PHRASES = (
    "standalone retrieval query",
    "based on the conversation",
    "here is",
    "sure,",
    "i can",
    "the user",
)
MAX_REWRITTEN_QUERY_CHARS = 240


@dataclass(frozen=True)
class QueryRewriteResult:
    original_query: str
    effective_query: str
    applied: bool
    model: str | None
    context_message_count: int


class RagQueryRewriter:
    def __init__(self, settings: Settings):
        self._enabled = settings.rag_query_rewrite_enabled
        self._model = settings.rag_query_rewrite_model.strip() or None
        self._history_limit = max(0, settings.rag_query_rewrite_history_messages)

    async def rewrite(
        self,
        *,
        query: str,
        history_messages: Sequence[dict[str, str]],
    ) -> QueryRewriteResult:
        original_query = query.strip()
        if not original_query:
            return QueryRewriteResult(
                original_query="",
                effective_query="",
                applied=False,
                model=self._model,
                context_message_count=0,
            )

        if not self._enabled or not self._model:
            return QueryRewriteResult(
                original_query=original_query,
                effective_query=original_query,
                applied=False,
                model=self._model,
                context_message_count=0,
            )

        context_messages = self._select_context_messages(history_messages)
        rewritten = _normalize_rewritten_query(
            await complete_model_response(
                model=self._model,
                requested_reasoning=False,
                messages=[
                    ChatMessagePayload(role="system", content=REWRITE_SYSTEM_PROMPT),
                    ChatMessagePayload(
                        role="user",
                        content=_build_rewrite_prompt(
                            current_query=original_query,
                            context_messages=context_messages,
                        ),
                    ),
                ],
            )
        )
        if not _is_valid_rewritten_query(original_query=original_query, rewritten=rewritten):
            rewritten = original_query

        return QueryRewriteResult(
            original_query=original_query,
            effective_query=rewritten,
            applied=rewritten != original_query,
            model=self._model,
            context_message_count=len(context_messages),
        )

    def _select_context_messages(self, history_messages: Sequence[dict[str, str]]) -> list[dict[str, str]]:
        if self._history_limit <= 0:
            return []

        collected: list[dict[str, str]] = []
        skipped_latest_user = False
        for message in reversed(history_messages):
            role = str(message.get("role", "")).strip()
            content = str(message.get("content", "")).strip()
            if role not in {"user", "assistant"} or not content:
                continue
            if not skipped_latest_user and role == "user":
                skipped_latest_user = True
                continue
            collected.append(
                {
                    "role": role,
                    "content": _truncate_content(content, limit=420),
                }
            )
            if len(collected) >= self._history_limit:
                break
        return list(reversed(collected))


def _build_rewrite_prompt(*, current_query: str, context_messages: Sequence[dict[str, str]]) -> str:
    if not context_messages:
        return f"Latest user request:\n{current_query}"

    context_block = "\n".join(
        f"{message['role']}: {message['content']}"
        for message in context_messages
    )
    return "\n\n".join(
        [
            "Recent conversation context:",
            context_block,
            "Latest user request:",
            current_query,
        ]
    )


def _normalize_rewritten_query(value: str) -> str:
    cleaned = value.replace("\r", "\n").strip().strip("`")
    first_line = cleaned.split("\n", 1)[0].strip()
    first_line = INVALID_PREFIX_PATTERN.sub("", first_line)
    return first_line.strip().strip('"').strip("'")


def _is_valid_rewritten_query(*, original_query: str, rewritten: str) -> bool:
    if not rewritten:
        return False
    if len(rewritten) > MAX_REWRITTEN_QUERY_CHARS:
        return False

    lowered = rewritten.lower()
    if any(phrase in lowered for phrase in INVALID_PHRASES):
        return False
    if lowered in {"same", "same question", "same query", "same as above"}:
        return False

    original_terms = _term_set(original_query)
    rewritten_terms = _term_set(rewritten)
    if original_terms and not (original_terms & rewritten_terms):
        return False
    return True


def _truncate_content(value: str, *, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


def _term_set(value: str) -> set[str]:
    return {term for term in re.findall(r"[A-Za-z0-9_.:+/#-]+|[\u4e00-\u9fff]{2,}", value.lower()) if term.strip()}
