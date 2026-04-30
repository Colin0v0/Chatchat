from __future__ import annotations

import re

from .classifier import extract_latin_subject
from ...cache import build_cache_key, get_json, set_json
from ...chat.types import ChatMessagePayload
from ...core.config import Settings
from ...runtime.model_runner import complete_model_response

TRANSLATION_SYSTEM_PROMPT = '''You are a professional Chinese (zh-Hans) to English (en) translator.
Accurately translate the user's Chinese search query into natural English.
Return only the English search query.
Do not explain the translation.
Do not add quotation marks.
'''
STOPWORDS = {
    'a', 'an', 'are', 'do', 'does', 'how', 'in', 'is', 'like', 'the', 'what', 'whats', "what's",
}
WORD_PATTERN = re.compile(r"[A-Za-z0-9.+-]+")
CJK_PATTERN = re.compile(r'[\u3400-\u9fff]')
INVALID_PHRASES = (
    'sorry',
    'assist with that',
    'cannot help',
    "can't help",
    'how can i assist',
    'hello',
    'please provide the chinese text',
    'please provide chinese text',
)
GENERIC_MUSIC_TOKENS = {'song', 'songs', 'time', 'who', 'by', 'singer', 'artist', 'title', 'music'}
MUSIC_LOOKUP_HINTS = ('谁唱', '是谁的歌', '歌', '演唱', '作词', '作曲')


class WebSearchTranslationError(RuntimeError):
    def __init__(self, *, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


async def translate_query_for_search(query: str, settings: Settings) -> str:
    cache_key = build_cache_key(
        settings,
        namespace="web_translate",
        version=1,
        payload={
            "model": settings.web_search_translation_model,
            "query": query.strip(),
            "prompt_version": "2026-04-29",
        },
    )
    cached = await get_json(settings, cache_key)
    if cached is not None:
        if not isinstance(cached, str):
            raise RuntimeError("Web translation cache entry must be a string.")
        return cached

    translated = _normalize_translation(
        await complete_model_response(
            model=settings.web_search_translation_model,
            messages=[
                ChatMessagePayload(role='system', content=TRANSLATION_SYSTEM_PROMPT),
                ChatMessagePayload(role='user', content=query),
            ],
        )
    )
    try:
        _ensure_translation_quality(query=query, translated=translated, model=settings.web_search_translation_model)
    except WebSearchTranslationError as exc:
        if exc.reason == 'underspecified':
            if extract_latin_subject(query):
                await _cache_translation(settings=settings, key=cache_key, translated=translated)
                return translated
            original = query.strip()
            await _cache_translation(settings=settings, key=cache_key, translated=original)
            return original
        raise
    await _cache_translation(settings=settings, key=cache_key, translated=translated)
    return translated


async def _cache_translation(*, settings: Settings, key: str, translated: str) -> None:
    # 翻译结果只依赖模型、提示词版本和原始查询，适合长 TTL 复用。
    await set_json(
        settings,
        key,
        translated,
        ttl_seconds=max(1, int(getattr(settings, "cache_web_translate_ttl_seconds", 604800))),
    )


def _normalize_translation(text: str) -> str:
    cleaned = text.replace('\r', '\n').strip().strip('"').strip("'")
    first_line = cleaned.split('\n', 1)[0].strip()
    if ':' in first_line and first_line.lower().startswith(('english', 'translation')):
        first_line = first_line.split(':', 1)[1].strip()

    words = WORD_PATTERN.findall(first_line)
    filtered = [word for word in words if word.lower() not in STOPWORDS]
    normalized = ' '.join(filtered)
    return ' '.join(normalized.split())


def _ensure_translation_quality(*, query: str, translated: str, model: str) -> None:
    if not translated:
        raise WebSearchTranslationError(
            reason='empty',
            message=f'Web translation failed: {model} returned an empty search query.',
        )

    lowered = translated.lower()
    if any(phrase in lowered for phrase in INVALID_PHRASES):
        raise WebSearchTranslationError(
            reason='invalid',
            message=f'Web translation failed: {model} produced an invalid search query.',
        )

    if CJK_PATTERN.search(translated):
        raise WebSearchTranslationError(
            reason='not_english',
            message=f'Web translation failed: {model} did not translate the query into English.',
        )

    if len(translated.split()) < 2:
        raise WebSearchTranslationError(
            reason='underspecified',
            message=f'Web translation failed: {model} produced an underspecified search query.',
        )

    if _looks_like_music_lookup(query) and not any(keyword in lowered for keyword in ('song', 'singer', 'artist', 'album', 'track', 'performed', 'written')):
        raise WebSearchTranslationError(
            reason='music_context_missing',
            message=f'Web translation failed: {model} did not preserve enough music-query context.',
        )

    tokens = [token.lower() for token in translated.split()]
    if _looks_like_music_lookup(query) and tokens and all(token in GENERIC_MUSIC_TOKENS for token in tokens):
        raise WebSearchTranslationError(
            reason='generic_music_query',
            message=f'Web translation failed: {model} produced a generic music search query without song identity.',
        )


def _looks_like_music_lookup(query: str) -> bool:
    return any(token in query for token in MUSIC_LOOKUP_HINTS)
