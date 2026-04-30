from __future__ import annotations

from dataclasses import replace

from .classifier import classify_web_intent, extract_latin_subject
from .query import contains_cjk, parse_web_query
from .rewriter import rewrite_web_query
from .rules import get_rule_for_intent
from .translator import translate_query_for_search
from .types import WebSearchPlan, WebQuery
from ...core.config import Settings

AI_MODEL_QUERY_HINTS = ("ai", "llm", "model", "models", "大模型", "模型", "人工智能")
AI_COMPANY_MARKERS = (
    "openai",
    "claude",
    "anthropic",
    "google",
    "gemini",
    "deepseek",
    "qwen",
    "minimax",
    "xiaomi",
    "glm",
    "kimi",
    "moonshot",
)


async def build_search_plan(raw_query: str, settings: Settings) -> WebSearchPlan:
    parsed = parse_web_query(raw_query)
    if not parsed.cleaned_query:
        return WebSearchPlan(query=parsed, queries=())

    intent = classify_web_intent(parsed.cleaned_query)
    translated_query = await _translate_if_needed(parsed, intent, settings)
    rewritten = rewrite_web_query(replace(parsed, intent=intent, translated_query=translated_query))
    return get_rule_for_intent(intent).build_plan(rewritten)


async def _translate_if_needed(query: WebQuery, intent: str, settings: Settings) -> str:
    if not contains_cjk(query.cleaned_query):
        return ""

    if _should_skip_translation(query.raw_query, intent):
        return ""

    return await translate_query_for_search(query.cleaned_query, settings)


def _should_skip_translation(raw_query: str, intent: str) -> bool:
    latin_subject = extract_latin_subject(raw_query)
    if not latin_subject:
        return False
    if _looks_like_mixed_ai_model_query(raw_query):
        return True
    return intent in {"music_entity_list", "entity_list", "stock"}


def _looks_like_mixed_ai_model_query(raw_query: str) -> bool:
    normalized = raw_query.lower()
    matched_companies = sum(1 for marker in AI_COMPANY_MARKERS if marker in normalized)
    return matched_companies >= 2 and any(hint in normalized for hint in AI_MODEL_QUERY_HINTS)
