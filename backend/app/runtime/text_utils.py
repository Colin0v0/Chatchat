from __future__ import annotations

import re

from ..chat.types import ChatMessagePayload

THINK_TAG_ONLY_PATTERN = re.compile(r"</?think>", re.IGNORECASE)


def strip_loose_think_tags(content: str) -> str:
    if not content:
        return content
    return THINK_TAG_ONLY_PATTERN.sub("", content)


def coalesce_leading_system_messages(messages: list[ChatMessagePayload]) -> list[ChatMessagePayload]:
    system_contents: list[str] = []
    consumed = 0
    for message in messages:
        if message.role != "system":
            break
        if message.images or message.documents or message.files:
            break
        system_contents.append(message.content.strip())
        consumed += 1

    if consumed <= 1:
        return messages

    merged_system = "\n\n".join(content for content in system_contents if content)
    return [ChatMessagePayload(role="system", content=merged_system), *messages[consumed:]]
