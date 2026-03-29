from __future__ import annotations

import re

from ...chat.types import ChatMessagePayload
from ...core.config import Settings
from ...llm import complete_chat, model_provider_and_name

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


async def translate_query_for_search(query: str, settings: Settings) -> str:
    provider, _ = model_provider_and_name(settings.web_search_translation_model)
    if provider != 'ollama':
        raise RuntimeError('WEB_SEARCH_TRANSLATION_MODEL must use an Ollama model.')

    translated = _normalize_translation(
        await complete_chat(
            model=settings.web_search_translation_model,
            messages=[
                ChatMessagePayload(role='system', content=TRANSLATION_SYSTEM_PROMPT),
                ChatMessagePayload(role='user', content=query),
            ],
        )
    )
    _ensure_translation_quality(query=query, translated=translated, model=settings.web_search_translation_model)
    return translated


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
        raise RuntimeError(f'Web translation failed: {model} returned an empty search query.')

    lowered = translated.lower()
    if any(phrase in lowered for phrase in INVALID_PHRASES):
        raise RuntimeError(f'Web translation failed: {model} produced an invalid search query.')

    if CJK_PATTERN.search(translated):
        raise RuntimeError(f'Web translation failed: {model} did not translate the query into English.')

    if len(translated.split()) < 2:
        raise RuntimeError(f'Web translation failed: {model} produced an underspecified search query.')

    if _looks_like_music_lookup(query) and not any(keyword in lowered for keyword in ('song', 'singer', 'artist', 'album', 'track', 'performed', 'written')):
        raise RuntimeError(f'Web translation failed: {model} did not preserve enough music-query context.')

    tokens = [token.lower() for token in translated.split()]
    if _looks_like_music_lookup(query) and tokens and all(token in GENERIC_MUSIC_TOKENS for token in tokens):
        raise RuntimeError(f'Web translation failed: {model} produced a generic music search query without song identity.')


def _looks_like_music_lookup(query: str) -> bool:
    return any(token in query for token in MUSIC_LOOKUP_HINTS)
