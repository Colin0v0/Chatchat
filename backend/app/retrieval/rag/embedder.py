from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from ...core.config import Settings
from .types import RagChunk, RagChunkSpec

logger = logging.getLogger("chatchat.embedding")


class KnowledgeEmbedder(Protocol):
    async def embed_query(self, query: str) -> list[float]:
        ...

    async def embed_chunk_specs(
        self, chunk_specs: list[RagChunkSpec]
    ) -> tuple[list[RagChunk], int]:
        ...


def build_knowledge_embedder(settings: Settings, embedding_model: str) -> KnowledgeEmbedder:
    normalized = embedding_model.strip()
    if not normalized:
        raise RuntimeError("KNOWLEDGE_EMBEDDING_MODEL is required for knowledge embedding.")
    provider = str(getattr(settings, "knowledge_embedding_provider", "dashscope")).strip().lower()
    if provider not in {"api", "openai", "openai-compatible", "openai_compatible", "dashscope"}:
        raise RuntimeError("Knowledge embedding only supports API providers. Set KNOWLEDGE_EMBEDDING_PROVIDER=dashscope.")
    return OpenAICompatibleEmbedder(settings, normalized)


@dataclass(frozen=True)
class ApiEmbeddingRuntime:
    base_url: str
    api_key: str
    model: str
    dimensions: int
    batch_size: int
    timeout_seconds: float


class OpenAICompatibleEmbedder:
    def __init__(self, settings: Settings, embedding_model: str):
        self._runtime = ApiEmbeddingRuntime(
            base_url=self._resolve_base_url(settings),
            api_key=self._resolve_api_key(settings),
            model=embedding_model,
            dimensions=max(1, int(getattr(settings, "knowledge_embedding_dimensions", 1024))),
            batch_size=max(1, int(getattr(settings, "knowledge_embedding_batch_size", 8))),
            timeout_seconds=max(1.0, float(getattr(settings, "knowledge_embedding_timeout_seconds", 30.0))),
        )

    async def embed_query(self, query: str) -> list[float]:
        embeddings = await self._embed_texts([query])
        return embeddings[0] if embeddings else []

    async def embed_chunk_specs(
        self, chunk_specs: list[RagChunkSpec]
    ) -> tuple[list[RagChunk], int]:
        if not chunk_specs:
            return [], 0

        texts = [f"{chunk.path}\n## {chunk.heading}\n{chunk.content}" for chunk in chunk_specs]
        embeddings = await self._embed_texts(texts)
        embedded_chunks = [
            RagChunk(
                id=chunk.id,
                path=chunk.path,
                directory=chunk.directory,
                heading=chunk.heading,
                content=chunk.content,
                order=chunk.order,
                embedding=embedding,
                tags=list(chunk.tags),
            )
            for chunk, embedding in zip(chunk_specs, embeddings)
        ]
        failed_chunks = max(0, len(chunk_specs) - len(embedded_chunks))
        return embedded_chunks, failed_chunks

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        normalized_texts = [text.strip() for text in texts if text.strip()]
        if not normalized_texts:
            return []

        vectors: list[list[float]] = []
        async with httpx.AsyncClient(
            base_url=self._runtime.base_url,
            headers=self._headers(),
            timeout=self._runtime.timeout_seconds,
        ) as client:
            for start in range(0, len(normalized_texts), self._runtime.batch_size):
                batch = normalized_texts[start : start + self._runtime.batch_size]
                response = await client.post(
                    "embeddings",
                    json=self._request_payload(batch),
                )
                response.raise_for_status()
                vectors.extend(self._parse_embeddings(response.json()))

        return vectors

    def _request_payload(self, batch: list[str]) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self._runtime.model,
            "input": batch,
        }
        if self._runtime.dimensions > 0:
            payload["dimensions"] = self._runtime.dimensions
        return payload

    def _parse_embeddings(self, payload: object) -> list[list[float]]:
        if not isinstance(payload, dict):
            raise RuntimeError("Embedding API returned a non-object response.")
        raw_items = payload.get("data")
        if not isinstance(raw_items, list):
            raise RuntimeError("Embedding API response did not include a data array.")

        sorted_items = sorted(
            [item for item in raw_items if isinstance(item, dict)],
            key=lambda item: int(item.get("index", 0)) if not isinstance(item.get("index"), bool) else 0,
        )
        vectors: list[list[float]] = []
        for item in sorted_items:
            raw_embedding = item.get("embedding")
            if not isinstance(raw_embedding, list):
                raise RuntimeError("Embedding API response included an invalid embedding.")
            vector = [float(value) for value in raw_embedding]
            if len(vector) != self._runtime.dimensions:
                raise RuntimeError(
                    "Embedding API returned an unexpected vector dimension. "
                    f"Expected {self._runtime.dimensions}, got {len(vector)}."
                )
            vectors.append(vector)
        return vectors

    def _headers(self) -> dict[str, str]:
        if not self._runtime.api_key:
            raise RuntimeError("KNOWLEDGE_EMBEDDING_API_KEY or DASHSCOPE_API_KEY is required for API embedding.")
        return {
            "Authorization": f"Bearer {self._runtime.api_key}",
            "Content-Type": "application/json",
        }

    def _resolve_base_url(self, settings: Settings) -> str:
        base_url = (
            str(getattr(settings, "knowledge_embedding_base_url", "")).strip()
            or str(getattr(settings, "dashscope_base_url", "")).strip()
        )
        if not base_url:
            raise RuntimeError("KNOWLEDGE_EMBEDDING_BASE_URL or DASHSCOPE_BASE_URL is required for API embedding.")
        return base_url.rstrip("/")

    def _resolve_api_key(self, settings: Settings) -> str:
        return (
            str(getattr(settings, "knowledge_embedding_api_key", "")).strip()
            or str(getattr(settings, "dashscope_api_key", "")).strip()
        )
