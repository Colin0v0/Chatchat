from __future__ import annotations

from ..llm import complete_chat
from .planner_parser import parse_tool_decision
from .planner_prompt import build_tool_planner_messages
from .planner_types import RetrievalPlan, ToolDecision
from .quick_decision import quick_decide_tool
from .strategy import NOTE_FIRST, PARALLEL_BALANCED, WEB_FIRST


class ToolPlannerService:
    async def plan(
        self,
        *,
        query: str,
        model: str,
        message_history: list[dict[str, str]],
        use_rag: bool,
        use_web: bool,
    ) -> RetrievalPlan:
        if not use_rag and not use_web:
            return build_retrieval_plan(
                decision=ToolDecision(tool="none", reason="No retrieval tools are enabled."),
                use_rag=use_rag,
                use_web=use_web,
            )

        quick_decision = quick_decide_tool(query)
        if quick_decision is not None:
            return build_retrieval_plan(
                decision=quick_decision,
                use_rag=use_rag,
                use_web=use_web,
            )

        messages = build_tool_planner_messages(
            query=query,
            message_history=message_history,
            use_rag=use_rag,
            use_web=use_web,
        )
        raw_response = await complete_chat(model=model, messages=messages)
        decision = parse_tool_decision(raw_response)
        return build_retrieval_plan(
            decision=decision,
            use_rag=use_rag,
            use_web=use_web,
        )


def build_retrieval_plan(
    *,
    decision: ToolDecision,
    use_rag: bool,
    use_web: bool,
) -> RetrievalPlan:
    if decision.tool == "rag_search":
        return RetrievalPlan(
            tool=decision.tool,
            reason=decision.reason,
            strategy=NOTE_FIRST,
            run_rag=use_rag,
            run_web=False,
            rag_query=decision.rag_query,
            web_query="",
        )

    if decision.tool == "web_search":
        return RetrievalPlan(
            tool=decision.tool,
            reason=decision.reason,
            strategy=WEB_FIRST,
            run_rag=False,
            run_web=use_web,
            rag_query="",
            web_query=decision.web_query,
        )

    if decision.tool == "both":
        return RetrievalPlan(
            tool=decision.tool,
            reason=decision.reason,
            strategy=PARALLEL_BALANCED,
            run_rag=use_rag,
            run_web=use_web,
            rag_query=decision.rag_query,
            web_query=decision.web_query,
        )

    return RetrievalPlan(
        tool="none",
        reason=decision.reason,
        strategy=PARALLEL_BALANCED,
        run_rag=False,
        run_web=False,
        rag_query="",
        web_query="",
    )
