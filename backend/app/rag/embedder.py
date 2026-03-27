from __future__ import annotations

import httpx

from ..config import Settings
from .types import RagChunk, RagChunkSpec


class OllamaEmbedder:
    def __init__(self, settings: Settings, embedding_model: str):
        self._settings = settings
        self._embedding_model = embedding_model
        self._base_url = settings.ollama_base_url.rstrip("/")

    async def embed_query(self, query: str) -> list[float]:
        timeout = httpx.Timeout(self._settings.request_timeout_seconds, connect=10.0)
        async with httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client:
            return await self._embed_text(client=client, text=query)

    async def embed_chunk_specs(
        self, chunk_specs: list[RagChunkSpec]
    ) -> tuple[list[RagChunk], int]:
        if not chunk_specs:
            return [], 0

        failed_chunks = 0
        embedded_chunks: list[RagChunk] = []
        timeout = httpx.Timeout(self._settings.request_timeout_seconds, connect=10.0)
        async with httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client:
            for chunk in chunk_specs:
                try:
                    embedding = await self._embed_text(
                        client=client,
                        text=f"{chunk.path}\n## {chunk.heading}\n{chunk.content}",
                    )
                except Exception:
                    failed_chunks += 1
                    continue

                embedded_chunks.append(
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
                )

        return embedded_chunks, failed_chunks

    async def _embed_text(self, *, client: httpx.AsyncClient, text: str) -> list[float]:
        payload = {
            "model": self._embedding_model,
            "input": text,
        }

        try:
            response = await client.post("/api/embed", json=payload)
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings")
            if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
                return [float(value) for value in embeddings[0]]
            embedding = data.get("embedding")
            if isinstance(embedding, list):
                return [float(value) for value in embedding]
        except httpx.HTTPError:
            pass

        fallback = await client.post(
            "/api/embeddings",
            json={
                "model": self._embedding_model,
                "prompt": text,
            },
        )
        fallback.raise_for_status()
        data = fallback.json()
        embedding = data.get("embedding")
        if not isinstance(embedding, list):
            raise ValueError("Invalid embedding payload returned by Ollama")
        return [float(value) for value in embedding]
