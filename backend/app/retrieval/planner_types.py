from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .strategy import RetrievalStrategy

ToolChoice = Literal["none", "rag_search", "web_search", "both"]


@dataclass(frozen=True)
class ToolDecision:
    tool: ToolChoice
    reason: str
    rag_query: str = ""
    web_query: str = ""


@dataclass(frozen=True)
class RetrievalPlan:
    tool: ToolChoice
    reason: str
    strategy: "RetrievalStrategy"
    run_rag: bool
    run_web: bool
    rag_query: str
    web_query: str
