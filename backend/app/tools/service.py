from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from ..chat.types import ChatMessagePayload
from ..core.config import Settings
from ..retrieval.file_context import ConversationFileContextService
from ..retrieval.language import prefers_simplified_chinese, response_language_instruction
from ..retrieval.query_rewrite import QueryRewriteResult, RagQueryRewriter
from ..retrieval.types import ContextEntry, ContextPayload, PromptContextPayload
from .plan import ToolContextPlan, build_tool_context_plan
from .requests import ToolContextBuildRequest, ToolPlanRequest

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ..knowledge import KnowledgeService
    from ..retrieval.websearch import WebSearchService
    from ..storage.models import Message


class ToolRuntimeService:
    def __init__(
        self,
        settings: Settings,
        knowledge_service: "KnowledgeService",
        web_search_service: "WebSearchService",
        file_context_service: ConversationFileContextService,
    ):
        self._knowledge_service = knowledge_service
        self._web_search_service = web_search_service
        self._file_context_service = file_context_service
        self._context_top_k = max(1, settings.retrieval_context_top_k)
        self._rag_query_rewriter = RagQueryRewriter(settings)

    def plan_context(
        self,
        *,
        request: ToolPlanRequest,
    ) -> ToolContextPlan:
        return build_tool_context_plan(query=request.query, policy=request.tool_policy)

    async def build_context_payload(
        self,
        *,
        request: ToolContextBuildRequest,
    ) -> PromptContextPayload:
        rewrite_result = await self._rewrite_query(plan=request.plan, retrieval_messages=request.retrieval_messages)
        debug = self._base_debug(
            plan=request.plan,
            rewrite_result=rewrite_result,
            include_file_context=request.include_file_context,
        )
        configuration_refusal = self._resolve_configuration_refusal(query=request.query, plan=request.plan)
        if configuration_refusal:
            return PromptContextPayload(
                context_message=None,
                should_refuse=True,
                refusal_message=configuration_refusal,
                debug=debug,
            )

        if not request.plan.policy.is_enabled and not request.include_file_context:
            return PromptContextPayload(context_message=None, debug=debug)

        tasks: list[asyncio.Future | asyncio.Task | object] = []
        if "knowledge" in request.plan.requested_tools:
            tasks.append(
                self._knowledge_service.retrieve_context(
                    db=request.db,
                    user_id=request.user_id,
                    query=rewrite_result.effective_query,
                    folders=list(request.plan.policy.knowledge_folders),
                )
            )
        if "search" in request.plan.requested_tools:
            tasks.append(self._web_search_service.retrieve_context(request.plan.query))
        if request.include_file_context:
            tasks.append(
                self._file_context_service.retrieve_context(
                    db=request.db,
                    query=request.query,
                    messages=request.conversation_messages,
                    include_images=request.include_image_context,
                )
            )

        results = await asyncio.gather(*tasks) if tasks else []
        merged_sources = self._merge_sources(results)
        merged_entries = self._merge_entries(results, strategy=request.plan.strategy)
        refusal_message = self._resolve_refusal_message(results, query=request.query)
        merged_debug = self._merge_debug(
            results,
            plan=request.plan,
            rewrite_result=rewrite_result,
            include_file_context=request.include_file_context,
        )
        merged_instructions = self._merge_instructions(results)

        if not merged_entries:
            if request.include_file_context:
                # Native multimodal requests may not need synthetic retrieval context.
                # In that case we should fall back to direct model reasoning instead of refusing.
                return PromptContextPayload(
                    context_message=None,
                    sources=[],
                    debug=merged_debug,
                )
            return PromptContextPayload(
                context_message=None,
                sources=[],
                should_refuse=True,
                refusal_message=refusal_message,
                debug=merged_debug,
            )

        return PromptContextPayload(
            context_message=self._build_context_message(
                query=request.query,
                entries=merged_entries,
                instructions=merged_instructions,
                plan=request.plan,
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

    def _merge_entries(self, results: list[ContextPayload], *, strategy) -> list[ContextEntry]:
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
                if entry.source.type == "file":
                    score += strategy.file_weight_bonus
                weighted_entries.append((score, entry))

        ranked = [item for _, item in sorted(weighted_entries, key=lambda pair: pair[0], reverse=True)]
        return ranked[: self._context_top_k]

    def _merge_instructions(self, results: list[ContextPayload]) -> tuple[str, ...]:
        instructions: list[str] = []
        for result in results:
            instructions.extend(result.instructions)
        return tuple(dict.fromkeys(item.strip() for item in instructions if item.strip()))

    async def _rewrite_query(
        self,
        *,
        plan: ToolContextPlan,
        retrieval_messages: list[dict[str, str]],
    ) -> QueryRewriteResult:
        if "knowledge" not in plan.requested_tools:
            return QueryRewriteResult(
                original_query=plan.query,
                effective_query=plan.query,
                applied=False,
                model=None,
                context_message_count=0,
            )
        return await self._rag_query_rewriter.rewrite(
            query=plan.query,
            history_messages=retrieval_messages,
        )

    def _base_debug(
        self,
        *,
        plan: ToolContextPlan,
        rewrite_result: QueryRewriteResult,
        include_file_context: bool,
    ) -> dict[str, object]:
        requested_tools = list(plan.requested_tools)
        if include_file_context:
            requested_tools.append("attachments")
        debug_payload = {
            "tool_strategy": plan.strategy.name,
            "tool_reason": plan.reason,
            "tool_query": rewrite_result.effective_query,
            "tool_query_original": rewrite_result.original_query,
            "knowledge_query_rewrite_applied": rewrite_result.applied,
            "knowledge_query_rewrite_model": rewrite_result.model,
            "knowledge_query_rewrite_context_messages": rewrite_result.context_message_count,
            "knowledge_executed": False,
            "search_executed": False,
            "file_executed": False,
        }
        debug_payload.update(plan.selection_payload)
        debug_payload["tool_plan"] = requested_tools
        return debug_payload

    def _merge_debug(
        self,
        results: list[ContextPayload],
        *,
        plan: ToolContextPlan,
        rewrite_result: QueryRewriteResult,
        include_file_context: bool,
    ) -> dict[str, object]:
        merged = self._base_debug(
            plan=plan,
            rewrite_result=rewrite_result,
            include_file_context=include_file_context,
        )
        merged["knowledge_executed"] = "knowledge" in plan.requested_tools
        merged["search_executed"] = "search" in plan.requested_tools
        merged["file_executed"] = any(result.debug.get("file_hits") is not None for result in results if result.debug)
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
            return "我没有找到足够可靠的依据来回答这个问题。可以缩小范围，或者调整工具模式。"
        return (
            "I could not find enough reliable supporting material for this question. "
            "Try narrowing the request or changing tool mode."
        )

    def _resolve_configuration_refusal(self, *, query: str, plan: ToolContextPlan) -> str | None:
        if "search" not in plan.requested_tools:
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
        plan: ToolContextPlan,
    ) -> ChatMessagePayload:
        blocks: list[str] = []
        for index, entry in enumerate(entries, start=1):
            source = entry.source
            fields = [f"[Source {index}]", f"type: {source.type}"]
            if source.type in {"note", "file"}:
                fields.append(f"path: {source.path}")
                if source.title:
                    fields.append(f"title: {source.title}")
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
            "When you rely on a note, cite its path. When you rely on a file, cite its filename or attachment name. When you rely on the web, cite the URL or site name. "
            "Do not cite the synthetic [Source N] labels in the final answer. "
            + response_language_instruction(query)
            + "\n"
            + plan.strategy.instruction
        )
        if instruction_block:
            content += "\nFollow these answer-mode instructions:\n" + instruction_block

        content += "\n\n" + "\n\n".join(blocks)
        return ChatMessagePayload(role="system", content=content)
