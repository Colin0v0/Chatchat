from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from ..core.config import Settings
from ..multimodal import ImageTextService
from ..retrieval.rag import RagService
from ..retrieval import RetrievalService, ToolPlannerService
from ..retrieval.websearch import WebSearchService


@dataclass(frozen=True)
class ChatServices:
    rag_service: RagService
    web_search_service: WebSearchService
    image_text_service: ImageTextService
    tool_planner_service: ToolPlannerService
    retrieval_service: RetrievalService


def build_chat_services(settings: Settings) -> ChatServices:
    rag_service = RagService(settings)
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
    )
    tool_planner_service = ToolPlannerService()
    retrieval_service = RetrievalService(
        settings,
        rag_service,
        web_search_service,
        tool_planner_service,
    )
    return ChatServices(
        rag_service=rag_service,
        web_search_service=web_search_service,
        image_text_service=image_text_service,
        tool_planner_service=tool_planner_service,
        retrieval_service=retrieval_service,
    )


def get_chat_services(request: Request) -> ChatServices:
    return request.app.state.chat_services
