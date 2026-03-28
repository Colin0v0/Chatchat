from __future__ import annotations

import re

CJK_PATTERN = re.compile(r'[\u3400-\u9fff]')


def prefers_simplified_chinese(query: str) -> bool:
    return bool(CJK_PATTERN.search(query))


def response_language_instruction(query: str) -> str:
    if prefers_simplified_chinese(query):
        return 'Respond in Simplified Chinese and format the answer as Markdown.'
    return 'Respond in the same language as the user query and format the answer as Markdown.'
