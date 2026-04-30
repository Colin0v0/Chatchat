from __future__ import annotations

from ..types import WebQuery, WebSearchPlan
from .base import VerticalRule, dedupe_queries

FRESHNESS_HINTS = (
    "latest",
    "current",
    "now",
    "today",
    "newest",
    "目前",
    "现在",
    "最新",
    "截至",
    "截止",
)
AI_MODEL_HINTS = (
    "ai",
    "llm",
    "model",
    "models",
    "大模型",
    "模型",
    "人工智能",
)
AI_COMPANY_QUERY_TERMS = {
    "openai": "OpenAI latest model",
    "anthropic": "Anthropic Claude latest model",
    "claude": "Anthropic Claude latest model",
    "google": "Google Gemini latest model",
    "gemini": "Google Gemini latest model",
    "deepseek": "DeepSeek latest model",
    "qwen": "Qwen latest model",
    "通义": "Qwen latest model",
    "minimax": "MiniMax latest model",
    "xiaomi": "Xiaomi latest AI model",
    "小米": "Xiaomi latest AI model",
    "glm": "GLM Zhipu latest model",
    "智谱": "GLM Zhipu latest model",
    "kimi": "Kimi Moonshot latest model",
    "moonshot": "Kimi Moonshot latest model",
}


class GenericRule(VerticalRule):
    def __init__(self) -> None:
        super().__init__(intent="general")

    def build_plan(self, query: WebQuery) -> WebSearchPlan:
        cleaned = query.cleaned_query.strip()
        company_queries = _ai_company_queries(cleaned)
        is_fresh_ai_model_lookup = _looks_like_fresh_ai_model_lookup(cleaned) and bool(company_queries)
        queries = dedupe_queries(cleaned, *company_queries)
        answer_instruction = "Answer directly from the most reliable sources. If evidence conflicts, say so plainly."
        debug_tags = ["generic"]
        score_floor = 0.35
        minimum_results = 1
        if is_fresh_ai_model_lookup:
            # 多家公司“最新模型”问题必须拆开查，否则一个超长查询很容易只命中泛文章。
            answer_instruction = (
                "Answer only from the provided web sources. For every company/model claim, cite the source URL "
                "or site name. If the sources do not prove the current latest model for a company, say it is not verified."
            )
            debug_tags.append("fresh_ai_models")
            score_floor = 0.28
            minimum_results = min(max(2, len(company_queries) // 2), 6)
        return WebSearchPlan(
            query=query,
            queries=queries,
            answer_mode="default",
            answer_instruction=answer_instruction,
            require_freshness=query.topic == "news" or is_fresh_ai_model_lookup,
            strict_refusal=False,
            minimum_results=minimum_results,
            score_floor=score_floor,
            debug_tags=tuple(debug_tags),
        )


def _looks_like_fresh_ai_model_lookup(query: str) -> bool:
    normalized = query.lower()
    return any(hint in normalized for hint in FRESHNESS_HINTS) and any(
        hint in normalized for hint in AI_MODEL_HINTS
    )


def _ai_company_queries(query: str) -> tuple[str, ...]:
    normalized = query.lower()
    queries: list[str] = []
    for marker, search_query in AI_COMPANY_QUERY_TERMS.items():
        if marker in normalized:
            queries.append(search_query)
    return tuple(dict.fromkeys(queries))
