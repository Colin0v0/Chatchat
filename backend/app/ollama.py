from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from .config import settings


async def stream_chat(
    *,
    model: str,
    messages: list[dict[str, str]],
) -> AsyncIterator[dict]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    timeout = httpx.Timeout(settings.request_timeout_seconds, connect=10.0)
    async with httpx.AsyncClient(base_url=settings.ollama_base_url, timeout=timeout) as client:
        async with client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                yield json.loads(line)
