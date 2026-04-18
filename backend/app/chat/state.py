from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from ..core.config import Settings
from ..knowledge import KnowledgeService
from ..memory.service import MemoryService
from ..multimodal.attachment import AttachmentContextService
from ..multimodal.file_parser import FileParser
from ..multimodal.image import ImageTextService
from ..retrieval.file_context import ConversationFileContextService
from ..retrieval.websearch import WebSearchService
from ..tools import ToolRuntimeService
from .model_queue import ModelExecutionCoordinator


@dataclass(frozen=True)
class ChatServices:
    knowledge_service: KnowledgeService
    web_search_service: WebSearchService
    memory_service: MemoryService
    attachment_context_service: AttachmentContextService
    tool_runtime: ToolRuntimeService
    history_message_limit: int
    history_token_budget: int
    summary_token_budget: int
    model_execution_coordinator: ModelExecutionCoordinator


def build_chat_services(settings: Settings) -> ChatServices:
    knowledge_service = KnowledgeService(settings)
    web_search_service = WebSearchService(settings)
    image_text_service = ImageTextService(
        min_confidence=settings.image_ocr_min_confidence,
        text_max_chars=settings.image_text_max_chars,
        vision_model_name=settings.image_vision_model,
        vision_prompt=settings.image_vision_prompt,
        vision_max_new_tokens=settings.image_vision_max_new_tokens,
        vision_num_beams=settings.image_vision_num_beams,
        vision_summary_max_chars=settings.image_vision_summary_max_chars,
        vision_device=settings.image_vision_device,
        idle_timeout_seconds=settings.local_model_idle_timeout_seconds,
    )
    attachment_context_service = AttachmentContextService(
        image_service=image_text_service,
        file_parser=FileParser(
            text_max_chars=settings.file_text_max_chars,
            table_row_limit=settings.file_table_row_limit,
            table_column_limit=settings.file_table_column_limit,
        ),
        max_concurrency=settings.attachment_processing_max_concurrency,
    )
    tool_runtime = ToolRuntimeService(
        settings,
        knowledge_service,
        web_search_service,
        ConversationFileContextService(settings, attachment_context_service),
    )
    memory_service = MemoryService(settings)
    return ChatServices(
        knowledge_service=knowledge_service,
        web_search_service=web_search_service,
        memory_service=memory_service,
        attachment_context_service=attachment_context_service,
        tool_runtime=tool_runtime,
        history_message_limit=max(1, settings.chat_history_message_limit),
        history_token_budget=max(256, settings.chat_history_token_budget),
        summary_token_budget=max(128, settings.chat_summary_token_budget),
        model_execution_coordinator=ModelExecutionCoordinator(
            max_concurrency_per_model=settings.model_max_concurrency_per_model,
        ),
    )


def get_chat_services(request: Request) -> ChatServices:
    return request.app.state.chat_services
