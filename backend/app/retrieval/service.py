from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ..chat.types import ChatMessagePayload
from ..core.config import Settings
from .language import prefers_simplified_chinese, response_language_instruction
from .plan import RetrievalMode, RetrievalPlan, build_retrieval_plan
from .strategy import RetrievalStrategy
from .types import ContextEntry, ContextPayload, PromptContextPayload

if TYPE_CHECKING:
    from .rag import RagService
    from .websearch import WebSearchService


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        rag_service: "RagService",
        web_search_service: "WebSearchService",
    ):
        self._rag_service = rag_service
        self._web_search_service = web_search_service
        self._context_top_k = max(1, settings.retrieval_context_top_k)

    def plan_retrieval(
        self,
        *,
        query: str,
        retrieval_mode: RetrievalMode,
    ) -> RetrievalPlan:
        return build_retrieval_plan(query=query, mode=retrieval_mode)

    async def build_context_payload(
        self,
        *,
        query: str,
        plan: RetrievalPlan,
    ) -> PromptContextPayload:
        debug = self._base_debug(plan=plan)
        configuration_refusal = self._resolve_configuration_refusal(query=query, plan=plan)
        if configuration_refusal:
            return PromptContextPayload(
                context_message=None,
                should_refuse=True,
                refusal_message=configuration_refusal,
                debug=debug,
            )

        if plan.mode == "none":
            return PromptContextPayload(context_message=None, debug=debug)

        tasks = []
        if plan.mode == "rag":
            tasks.append(self._rag_service.retrieve_context(plan.query))
        if plan.mode == "web":
            tasks.append(self._web_search_service.retrieve_context(plan.query))

        results = await asyncio.gather(*tasks)
        merged_sources = self._merge_sources(results)
        merged_entries = self._merge_entries(results, strategy=plan.strategy)
        refusal_message = self._resolve_refusal_message(results, query=query)
        merged_debug = self._merge_debug(results, plan=plan)
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

    def _base_debug(self, *, plan: RetrievalPlan) -> dict[str, object]:
        return {
            "retrieval_strategy": plan.strategy.name,
            "retrieval_mode": plan.mode,
            "retrieval_reason": plan.reason,
            "retrieval_query": plan.query,
            "rag_executed": False,
            "web_executed": False,
        }

    def _merge_debug(self, results: list[ContextPayload], *, plan: RetrievalPlan) -> dict[str, object]:
        merged = self._base_debug(plan=plan)
        merged["rag_executed"] = plan.mode == "rag"
        merged["web_executed"] = plan.mode == "web"
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
            return "我没有找到足够可靠的依据来回答这个问题。可以缩小范围，或者切换检索模式。"
        return (
            "I could not find enough reliable supporting material for this question. "
            "Try narrowing the request or switching retrieval mode."
        )

    def _resolve_configuration_refusal(self, *, query: str, plan: RetrievalPlan) -> str | None:
        if plan.mode != "web":
            return None

        try:
            self._web_search_service.require_configuration()
        except RuntimeError:
            if prefers_simplified_chinese(query):
                return "当前 Search 模式还没配置好，暂时不能联网搜索。先配置 Tavily API Key。"
            return "Search mode is not configured yet. Configure the Tavily API key first."
        return None

    def _build_context_message(
        self,
        *,
        query: str,
        entries: list[ContextEntry],
        instructions: tuple[str, ...],
        strategy: RetrievalStrategy,
    ) -> ChatMessagePayload:
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
        return ChatMessagePayload(role="system", content=content)
