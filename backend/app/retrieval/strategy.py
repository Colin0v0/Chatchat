from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class RetrievalStrategy:
    name: str
    rag_weight_bonus: float = 0.0
    web_weight_bonus: float = 0.0
    instruction: str = ""


DIRECT_ANSWER = RetrievalStrategy(
    name="direct",
    instruction="",
)
NOTE_FIRST = RetrievalStrategy(
    name="note-first",
    rag_weight_bonus=0.10,
    web_weight_bonus=-0.02,
    instruction="Prefer note references when they directly answer the question. Use web references only as supporting context.",
)
WEB_FIRST = RetrievalStrategy(
    name="web-first",
    rag_weight_bonus=-0.02,
    web_weight_bonus=0.10,
    instruction="Prefer web references for public, freshness-sensitive, or lookup-style questions. Use notes only as supporting context.",
)
