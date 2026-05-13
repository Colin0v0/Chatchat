from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

from ..cache import build_cache_key, get_json, set_json
from ..chat.types import ChatMessagePayload
from ..core.config import Settings
from ..runtime.model_runner import complete_model_response

REWRITE_SYSTEM_PROMPT = """You rewrite the latest user request into a standalone retrieval/search query for retrieval tools.
Preserve the user's intent, entities, filenames, dates, version numbers, error messages, APIs, and code symbols.
Resolve references such as it, that, this plan, 这个, 那个, 上面那个 using the recent conversation when needed.
Use relevant saved memory and past-chat hints only when they clarify entities, projects, preferences, location, time range, or domain.
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
    memory_hint_count: int = 0


class RagQueryRewriter:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._enabled = settings.rag_query_rewrite_enabled
        self._model = settings.rag_query_rewrite_model.strip() or None
        self._history_limit = max(0, settings.rag_query_rewrite_history_messages)

    async def rewrite(
        self,
        *,
        query: str,
        history_messages: Sequence[dict[str, str]],
        memory_query_hints: Sequence[str] = (),
    ) -> QueryRewriteResult:
        original_query = query.strip()
        if not original_query:
            return QueryRewriteResult(
                original_query="",
                effective_query="",
                applied=False,
                model=self._model,
                context_message_count=0,
                memory_hint_count=0,
            )

        if not self._enabled:
            return QueryRewriteResult(
                original_query=original_query,
                effective_query=original_query,
                applied=False,
                model=self._model,
                context_message_count=0,
                memory_hint_count=0,
            )

        context_messages = self._select_context_messages(history_messages)
        memory_hints = _select_memory_hints(memory_query_hints)
        if not self._model:
            return QueryRewriteResult(
                original_query=original_query,
                effective_query=original_query,
                applied=False,
                model=None,
                context_message_count=len(context_messages),
                memory_hint_count=0,
            )
        cache_key = build_cache_key(
            self._settings,
            namespace="rag_query_rewrite",
            version=2,
            payload={
                "model": self._model,
                "query": original_query,
                "context_messages": context_messages,
                "memory_hints": memory_hints,
                "prompt_version": "2026-05-12",
            },
        )
        cached = await get_json(self._settings, cache_key)
        if cached is not None:
            if not isinstance(cached, str):
                raise RuntimeError("RAG query rewrite cache entry must be a string.")
            return QueryRewriteResult(
                original_query=original_query,
                effective_query=cached,
                applied=cached != original_query,
                model=self._model,
                context_message_count=len(context_messages),
                memory_hint_count=len(memory_hints),
            )

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
                            memory_hints=memory_hints,
                        ),
                    ),
                ],
            )
        )
        if not _is_valid_rewritten_query(original_query=original_query, rewritten=rewritten):
            rewritten = original_query

        # 查询改写由近期上下文和提示词版本完全决定，缓存后可以减少一次模型调用。
        await set_json(
            self._settings,
            cache_key,
            rewritten,
            ttl_seconds=max(1, int(getattr(self._settings, "cache_rag_query_rewrite_ttl_seconds", 21600))),
        )

        return QueryRewriteResult(
            original_query=original_query,
            effective_query=rewritten,
            applied=rewritten != original_query,
            model=self._model,
            context_message_count=len(context_messages),
            memory_hint_count=len(memory_hints),
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


def _build_rewrite_prompt(
    *,
    current_query: str,
    context_messages: Sequence[dict[str, str]],
    memory_hints: Sequence[str] = (),
) -> str:
    blocks: list[str] = []

    if memory_hints:
        blocks.extend(
            [
                "Relevant saved memory and past-chat hints:",
                "\n".join(f"- {hint}" for hint in memory_hints),
            ]
        )

    if context_messages:
        context_block = "\n".join(
            f"{message['role']}: {message['content']}"
            for message in context_messages
        )
        blocks.extend(
            [
            "Recent conversation context:",
            context_block,
            ]
        )

    blocks.extend(["Latest user request:", current_query])
    return "\n\n".join(blocks)


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


def _select_memory_hints(values: Sequence[str]) -> list[str]:
    hints: list[str] = []
    for value in values:
        normalized = _truncate_content(str(value), limit=180)
        if normalized and normalized not in hints:
            hints.append(normalized)
        if len(hints) >= 5:
            break
    return hints


def _term_set(value: str) -> set[str]:
    terms: set[str] = set()
    for raw_term in re.findall(r"[A-Za-z0-9_.:+/#-]+|[\u4e00-\u9fff]{2,}", value.lower()):
        term = raw_term.strip()
        if not term:
            continue
        terms.add(term)
        if _is_chinese_term(term):
            # 中文没有天然空格，加入短片段后才能识别“这个面板”与“候选记忆面板”的共同实体。
            for size in (2, 3):
                if len(term) <= size:
                    continue
                terms.update(term[index : index + size] for index in range(len(term) - size + 1))
    return terms


def _is_chinese_term(value: str) -> bool:
    return bool(value) and all("\u4e00" <= char <= "\u9fff" for char in value)
