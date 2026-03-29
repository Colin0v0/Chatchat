from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .strategy import DIRECT_ANSWER, NOTE_FIRST, WEB_FIRST

if TYPE_CHECKING:
    from .strategy import RetrievalStrategy


RetrievalMode = Literal["none", "rag", "web"]


@dataclass(frozen=True)
class RetrievalPlan:
    mode: RetrievalMode
    reason: str
    strategy: "RetrievalStrategy"
    query: str = ""


def build_retrieval_plan(*, query: str, mode: RetrievalMode) -> RetrievalPlan:
    normalized_query = query.strip()
    if mode == "none":
        return RetrievalPlan(
            mode="none",
            reason="Retrieval mode is off.",
            strategy=DIRECT_ANSWER,
            query="",
        )

    if not normalized_query:
        return RetrievalPlan(
            mode="none",
            reason="No text query provided.",
            strategy=DIRECT_ANSWER,
            query="",
        )

    if mode == "rag":
        return RetrievalPlan(
            mode="rag",
            reason="RAG mode selected.",
            strategy=NOTE_FIRST,
            query=normalized_query,
        )

    return RetrievalPlan(
        mode="web",
        reason="Web mode selected.",
        strategy=WEB_FIRST,
        query=normalized_query,
    )
