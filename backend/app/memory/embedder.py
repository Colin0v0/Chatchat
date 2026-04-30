from __future__ import annotations

import logging

from ..core.config import Settings
from ..retrieval.rag.embedder import OpenAICompatibleEmbedder

logger = logging.getLogger("chatchat.memory")


class MemoryEmbedder:
    """Thin wrapper around OpenAICompatibleEmbedder for memory-specific embedding.

    Reuses the knowledge embedding infrastructure (model, base_url, api_key, cache).
    Memory text is formatted as ``title\ndetail\ntags`` for semantic retrieval.
    """

    def __init__(self, settings: Settings):
        self._inner = OpenAICompatibleEmbedder(settings, settings.knowledge_embedding_model)

    def _memory_text(self, title: str, detail: str, tags: list[str]) -> str:
        parts = [title.strip()]
        if detail and detail.strip():
            parts.append(detail.strip())
        if tags:
            parts.append(" ".join(f"#{t}" for t in tags if t.strip()))
        return "\n".join(parts)

    async def embed_memory(
        self,
        *,
        title: str,
        detail: str = "",
        tags: list[str] | None = None,
    ) -> list[float]:
        text = self._memory_text(title, detail, tags or [])
        return await self._inner.embed_query(text)

    async def embed_query(self, query: str) -> list[float]:
        return await self._inner.embed_query(query)
