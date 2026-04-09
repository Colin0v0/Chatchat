from __future__ import annotations

import time

import httpx

from ...core.config import Settings
from ...core.http import limited_request, shared_http_clients
from ...llm.ollama_runtime import log_ollama_request, ollama_keep_alive_value
from .types import RagChunk, RagChunkSpec


class OllamaEmbedder:
    def __init__(self, settings: Settings, embedding_model: str):
        self._settings = settings
        self._embedding_model = embedding_model
        self._base_url = settings.ollama_base_url.rstrip("/")

    async def embed_query(self, query: str) -> list[float]:
        client = await self._client()
        async with limited_request(gate="ollama", max_concurrency=self._settings.ollama_http_max_concurrency):
            return await self._embed_text(client=client, text=query)

    async def embed_chunk_specs(
        self, chunk_specs: list[RagChunkSpec]
    ) -> tuple[list[RagChunk], int]:
        if not chunk_specs:
            return [], 0

        failed_chunks = 0
        embedded_chunks: list[RagChunk] = []
        client = await self._client()
        async with limited_request(gate="ollama", max_concurrency=self._settings.ollama_http_max_concurrency):
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

    async def _client(self) -> httpx.AsyncClient:
        return await shared_http_clients.get_client(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._settings.request_timeout_seconds, connect=10.0),
            limits=httpx.Limits(
                max_connections=max(1, self._settings.http_pool_max_connections),
                max_keepalive_connections=max(1, self._settings.http_pool_max_keepalive_connections),
            ),
        )

    async def _embed_text(self, *, client: httpx.AsyncClient, text: str) -> list[float]:
        keep_alive = ollama_keep_alive_value(self._settings.ollama_keep_alive_seconds)
        payload = {
            "model": self._embedding_model,
            "input": text,
            "keep_alive": keep_alive,
        }
        started_at = time.perf_counter()

        try:
            response = await client.post("/api/embed", json=payload)
            response.raise_for_status()
            data = response.json()
            log_ollama_request(
                kind="embed",
                model=self._embedding_model,
                keep_alive=keep_alive,
                started_at=started_at,
                response_payload=data,
            )
            embeddings = data.get("embeddings")
            if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
                return [float(value) for value in embeddings[0]]
            embedding = data.get("embedding")
            if isinstance(embedding, list):
                return [float(value) for value in embedding]
        except httpx.HTTPError:
            raise

        raise ValueError("Invalid embedding payload returned by Ollama /api/embed")
