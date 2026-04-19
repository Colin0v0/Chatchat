from __future__ import annotations

from dataclasses import dataclass

from ..retrieval.strategy import DIRECT_ANSWER, NOTE_FIRST, WEB_FIRST, RetrievalStrategy
from .policy import ContextTool, ToolPolicy, build_tool_policy


@dataclass(frozen=True)
class ToolContextPlan:
    policy: ToolPolicy
    reason: str
    strategy: RetrievalStrategy
    query: str = ""

    @property
    def mode(self) -> str:
        return self.policy.source_mode

    @property
    def requested_tools(self) -> tuple[ContextTool, ...]:
        return self.policy.requested_tools

    @property
    def selection_payload(self) -> dict[str, object]:
        return self.policy.to_context_payload()


def build_tool_context_plan(*, query: str, policy: ToolPolicy) -> ToolContextPlan:
    normalized_query = query.strip()
    if not policy.is_enabled:
        return ToolContextPlan(
            policy=policy,
            reason="Tool grounding is off.",
            strategy=DIRECT_ANSWER,
            query="",
        )

    if not normalized_query:
        return ToolContextPlan(
            policy=build_tool_policy("none"),
            reason="No text query provided.",
            strategy=DIRECT_ANSWER,
            query="",
        )

    if policy.mode == "knowledge":
        return ToolContextPlan(
            policy=policy,
            reason="Knowledge grounding selected.",
            strategy=NOTE_FIRST,
            query=normalized_query,
        )

    return ToolContextPlan(
        policy=policy,
        reason="Search grounding selected.",
        strategy=WEB_FIRST,
        query=normalized_query,
    )
