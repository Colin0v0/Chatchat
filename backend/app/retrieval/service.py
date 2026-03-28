from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ..config import Settings
from .language import prefers_simplified_chinese, response_language_instruction
from .planner_types import RetrievalPlan
from .strategy import RetrievalStrategy
from .types import ContextEntry, ContextPayload, PromptContextPayload

if TYPE_CHECKING:
    from ..rag import RagService
    from ..websearch import WebSearchService
    from .planner import ToolPlannerService


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        rag_service: RagService,
        web_search_service: WebSearchService,
        tool_planner_service: ToolPlannerService,
    ):
        self._settings = settings
        self._rag_service = rag_service
        self._web_search_service = web_search_service
        self._tool_planner_service = tool_planner_service
        self._context_top_k = max(1, settings.retrieval_context_top_k)

    async def plan_retrieval(
        self,
        *,
        query: str,
        model: str,
        message_history: list[dict[str, str]],
        use_rag: bool,
        use_web: bool,
    ) -> RetrievalPlan:
        return await self._tool_planner_service.plan(
            query=query,
            model=model,
            message_history=message_history,
            use_rag=use_rag,
            use_web=use_web,
        )

    async def build_context_payload(
        self,
        *,
        query: str,
        plan: RetrievalPlan,
        use_rag: bool,
        use_web: bool,
    ) -> PromptContextPayload:
        debug = self._base_debug(plan=plan, rag_enabled=use_rag, web_enabled=use_web)
        disabled_capability_refusal = self._resolve_disabled_capability_refusal(
            query=query,
            plan=plan,
            use_rag=use_rag,
            use_web=use_web,
        )
        if disabled_capability_refusal:
            return PromptContextPayload(
                context_message=None,
                should_refuse=True,
                refusal_message=disabled_capability_refusal,
                debug=debug,
            )

        configuration_refusal = self._resolve_configuration_refusal(query=query, plan=plan)
        if configuration_refusal:
            return PromptContextPayload(
                context_message=None,
                should_refuse=True,
                refusal_message=configuration_refusal,
                debug=debug,
            )

        if plan.tool == "none":
            return PromptContextPayload(context_message=None, debug=debug)

        tasks = []
        if plan.run_rag:
            tasks.append(self._rag_service.retrieve_context(plan.rag_query))
        if plan.run_web:
            tasks.append(self._web_search_service.retrieve_context(plan.web_query))

        results = await asyncio.gather(*tasks)
        merged_sources = self._merge_sources(results)
        merged_entries = self._merge_entries(results, strategy=plan.strategy)
        refusal_message = self._resolve_refusal_message(results, query=query)
        merged_debug = self._merge_debug(
            results,
            plan=plan,
            rag_enabled=use_rag,
            web_enabled=use_web,
        )
        merged_instructions = self._merge_instructions(results)

        if not merged_entries:
            return PromptContextPayload(
                context_message=None,
                sources=[],
                should_refuse=True,
                refusal_message=refusal_message,
                debug=merged_debug,
            )

        return PromptContextPayload(
            context_message=self._build_context_message(
                query=query,
                entries=merged_entries,
                instructions=merged_instructions,
                strategy=plan.strategy,
            ),
            sources=[source.to_payload() for source in merged_sources],
            debug=merged_debug,
        )

    def _merge_sources(self, results: list[ContextPayload]) -> list:
        unique: dict[tuple[str, str, str], object] = {}
        for result in results:
            for source in result.sources:
                key = (source.type, source.path, source.url)
                previous = unique.get(key)
                if previous is None or (source.score or 0.0) > (previous.score or 0.0):
                    unique[key] = source

        ranked = sorted(unique.values(), key=lambda item: item.score or 0.0, reverse=True)
        return ranked[: self._context_top_k]

    def _merge_entries(self, results: list[ContextPayload], *, strategy: RetrievalStrategy) -> list[ContextEntry]:
        weighted_entries: list[tuple[float, ContextEntry]] = []
        for result in results:
            for entry in result.entries:
                if not entry.content.strip():
                    continue
                score = entry.source.score or 0.0
                if entry.source.type == "web":
                    score += strategy.web_weight_bonus
                if entry.source.type == "note":
                    score += strategy.rag_weight_bonus
                weighted_entries.append((score, entry))

        ranked = [item for _, item in sorted(weighted_entries, key=lambda pair: pair[0], reverse=True)]
        return ranked[: self._context_top_k]

    def _merge_instructions(self, results: list[ContextPayload]) -> tuple[str, ...]:
        instructions: list[str] = []
        for result in results:
            instructions.extend(result.instructions)
        return tuple(dict.fromkeys(item.strip() for item in instructions if item.strip()))

    def _base_debug(self, *, plan: RetrievalPlan, rag_enabled: bool, web_enabled: bool) -> dict[str, object]:
        return {
            "retrieval_strategy": plan.strategy.name,
            "planner_tool": plan.tool,
            "planner_reason": plan.reason,
            "rag_enabled": rag_enabled,
            "web_enabled": web_enabled,
            "rag_executed": False,
            "web_executed": False,
            "rag_query": plan.rag_query,
            "web_query": plan.web_query,
        }

    def _merge_debug(
        self,
        results: list[ContextPayload],
        *,
        plan: RetrievalPlan,
        rag_enabled: bool,
        web_enabled: bool,
    ) -> dict[str, object]:
        merged = self._base_debug(plan=plan, rag_enabled=rag_enabled, web_enabled=web_enabled)
        merged["rag_executed"] = plan.run_rag
        merged["web_executed"] = plan.run_web
        for result in results:
            if not result.debug:
                continue
            for key, value in result.debug.items():
                merged[key] = value
        return merged

    def _resolve_refusal_message(self, results: list[ContextPayload], *, query: str) -> str:
        for result in results:
            if result.refusal_message:
                return result.refusal_message
        if prefers_simplified_chinese(query):
            return "我没有找到足够可靠的依据来回答这个问题。可以缩小范围，或者开启更合适的检索方式。"
        return (
            "I could not find enough reliable supporting material for this question. "
            "Try narrowing the request or enabling a different retrieval mode."
        )

    def _resolve_disabled_capability_refusal(
        self,
        *,
        query: str,
        plan: RetrievalPlan,
        use_rag: bool,
        use_web: bool,
    ) -> str | None:
        missing: list[str] = []
        if plan.tool in {"rag_search", "both"} and not use_rag:
            missing.append("RAG")
        if plan.tool in {"web_search", "both"} and not use_web:
            missing.append("Web")
        if not missing:
            return None

        missing_text = " 和 ".join(missing) if prefers_simplified_chinese(query) else " and ".join(missing)
        if prefers_simplified_chinese(query):
            return f"这个问题需要 {missing_text}，但当前没有开启。先开启后再试一次。"
        return f"This question needs {missing_text}, but it is currently disabled. Enable it and try again."

    def _resolve_configuration_refusal(self, *, query: str, plan: RetrievalPlan) -> str | None:
        if not plan.run_web:
            return None

        try:
            self._web_search_service.require_configuration()
        except RuntimeError:
            if prefers_simplified_chinese(query):
                return "当前 Web 工具还没配置好，暂时不能联网搜索。先配置 Tavily API Key。"
            return "The Web tool is not configured yet. Configure the Tavily API key first."
        return None

    def _build_context_message(
        self,
        *,
        query: str,
        entries: list[ContextEntry],
        instructions: tuple[str, ...],
        strategy: RetrievalStrategy,
    ) -> dict[str, str]:
        blocks: list[str] = []
        for index, entry in enumerate(entries, start=1):
            source = entry.source
            fields = [f"[Source {index}]", f"type: {source.type}"]
            if source.type == "note":
                fields.append(f"path: {source.path}")
                if source.heading:
                    fields.append(f"heading: {source.heading}")
            else:
                if source.title:
                    fields.append(f"title: {source.title}")
                if source.url:
                    fields.append(f"url: {source.url}")
                if source.domain:
                    fields.append(f"domain: {source.domain}")
                if source.published_at:
                    fields.append(f"published_at: {source.published_at}")
                if source.trust:
                    fields.append(f"trust: {source.trust}")
                if source.freshness:
                    fields.append(f"freshness: {source.freshness}")
                if source.match_reason:
                    fields.append(f"match_reason: {source.match_reason}")
            fields.extend(["content:", entry.content])
            blocks.append("\n".join(fields))

        instruction_block = "\n".join(f"- {instruction}" for instruction in instructions)
        content = (
            "Use the following references when answering. "
            "If the evidence is insufficient, say so plainly. "
            "When you rely on a note, cite its path. When you rely on the web, cite the URL or site name. "
            "Do not cite the synthetic [Source N] labels in the final answer. "
            + response_language_instruction(query)
            + "\n"
            + strategy.instruction
        )
        if instruction_block:
            content += "\nFollow these answer-mode instructions:\n" + instruction_block

        content += "\n\n" + "\n\n".join(blocks)
        return {
            "role": "system",
            "content": content,
        }
