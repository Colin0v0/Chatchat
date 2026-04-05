from __future__ import annotations

from dataclasses import dataclass

from ..retrieval import RetrievalMode


@dataclass(frozen=True)
class ContextStrategy:
    name: str
    history_token_budget: int
    summary_token_budget: int
    file_retrieval_enabled: bool


def choose_context_strategy(
    *,
    query: str,
    retrieval_mode: RetrievalMode,
    has_conversation_attachments: bool,
    default_history_budget: int,
    default_summary_budget: int,
) -> ContextStrategy:
    normalized_query = query.strip()
    is_long_query = len(normalized_query) >= 120

    if retrieval_mode == "web":
        return ContextStrategy(
            name="web-grounded",
            history_token_budget=max(900, int(default_history_budget * 0.75)),
            summary_token_budget=max(400, int(default_summary_budget * 0.75)),
            file_retrieval_enabled=has_conversation_attachments,
        )

    if retrieval_mode == "rag":
        return ContextStrategy(
            name="note-grounded",
            history_token_budget=max(1100, int(default_history_budget * 0.82)),
            summary_token_budget=max(500, int(default_summary_budget * 0.82)),
            file_retrieval_enabled=has_conversation_attachments,
        )

    if has_conversation_attachments:
        return ContextStrategy(
            name="attachment-aware",
            history_token_budget=max(1200, int(default_history_budget * 0.9)),
            summary_token_budget=max(550, int(default_summary_budget * 0.85)),
            file_retrieval_enabled=True,
        )

    if is_long_query:
        return ContextStrategy(
            name="long-context",
            history_token_budget=int(default_history_budget * 1.1),
            summary_token_budget=int(default_summary_budget * 1.15),
            file_retrieval_enabled=False,
        )

    return ContextStrategy(
        name="balanced",
        history_token_budget=default_history_budget,
        summary_token_budget=default_summary_budget,
        file_retrieval_enabled=False,
    )
