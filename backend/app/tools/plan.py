from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..retrieval.strategy import DIRECT_ANSWER, NOTE_FIRST, WEB_FIRST, RetrievalStrategy
from ..schemas import ToolMode

ContextTool = Literal["knowledge", "search"]


@dataclass(frozen=True)
class ToolContextPlan:
    mode: ToolMode
    reason: str
    strategy: RetrievalStrategy
    query: str = ""
    requested_tools: tuple[ContextTool, ...] = ()


def build_tool_context_plan(*, query: str, mode: ToolMode) -> ToolContextPlan:
    normalized_query = query.strip()
    if mode == "none":
        return ToolContextPlan(
            mode="none",
            reason="Tool grounding is off.",
            strategy=DIRECT_ANSWER,
            query="",
            requested_tools=(),
        )

    if not normalized_query:
        return ToolContextPlan(
            mode="none",
            reason="No text query provided.",
            strategy=DIRECT_ANSWER,
            query="",
            requested_tools=(),
        )

    if mode == "knowledge":
        return ToolContextPlan(
            mode="knowledge",
            reason="Knowledge grounding selected.",
            strategy=NOTE_FIRST,
            query=normalized_query,
            requested_tools=("knowledge",),
        )

    return ToolContextPlan(
        mode="search",
        reason="Search grounding selected.",
        strategy=WEB_FIRST,
        query=normalized_query,
        requested_tools=("search",),
    )
