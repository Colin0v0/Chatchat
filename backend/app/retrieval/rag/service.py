from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...core.config import Settings
from ..language import prefers_simplified_chinese
from ..types import ContextEntry, ContextPayload, SourceItem
from .chunking import build_chunk_specs_for_document, collect_markdown_documents
from .embedder import OllamaEmbedder
from .neighbors import expand_neighbor_chunks
from .query_filters import parse_query_filters
from .reranker import LexicalReranker
from .retriever import HybridRetriever
from .store import RagIndexStore
from .types import QueryFilters, RagChunk, RagContextPayload, RetrievalCandidate


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class RagService:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._vault_path = Path(settings.rag_vault_path).expanduser()
        self._index_path = Path(settings.rag_index_path).expanduser()
        self._embedding_model = settings.rag_embedding_model
        self._top_k = max(1, settings.rag_top_k)
        self._section_max_chars = max(400, settings.rag_section_max_chars)
        self._candidate_limit = max(self._top_k, settings.rag_candidate_limit)
        self._rerank_window = max(self._top_k, settings.rag_rerank_window)
        self._neighbor_window = max(0, settings.rag_neighbor_window)
        self._min_score = max(0.0, settings.rag_min_score)
        self._lock = asyncio.Lock()

        self._chunks: list[RagChunk] = []
        self._chunks_by_path: dict[str, list[RagChunk]] = {}
        self._updated_at: str | None = None
        self._file_signatures: dict[str, str] = {}
        self._index_embedding_model: str | None = None
        self._index_section_max_chars: int | None = None

        self._store = RagIndexStore(self._index_path)
        self._embedder = OllamaEmbedder(settings, self._embedding_model)
        self._retriever = HybridRetriever()
        self._reranker = LexicalReranker(rerank_window=self._rerank_window)
        self._load_index_from_disk()

    def status(self) -> dict[str, Any]:
        return {
            "vault_path": str(self._vault_path),
            "index_path": str(self._index_path),
            "embedding_model": self._embedding_model,
            "top_k": self._top_k,
            "section_max_chars": self._section_max_chars,
            "candidate_limit": self._candidate_limit,
            "rerank_window": self._rerank_window,
            "neighbor_window": self._neighbor_window,
            "min_score": self._min_score,
            "chunk_count": len(self._chunks),
            "updated_at": self._updated_at,
            "vault_exists": self._vault_path.exists(),
        }

    async def reindex(self) -> dict[str, Any]:
        async with self._lock:
            documents = collect_markdown_documents(self._vault_path)
            current_signatures = {document.path: document.signature for document in documents}
            current_paths = set(current_signatures)

            can_reuse_chunks = self._can_reuse_chunks()
            if can_reuse_chunks:
                changed_paths = {
                    path
                    for path, signature in current_signatures.items()
                    if self._file_signatures.get(path) != signature
                }
                unchanged_paths = current_paths - changed_paths
            else:
                changed_paths = set(current_paths)
                unchanged_paths = set()

            reused_chunks = [chunk for chunk in self._chunks if chunk.path in unchanged_paths]
            chunk_specs_to_embed = []
            for document in documents:
                if document.path in changed_paths:
                    chunk_specs_to_embed.extend(
                        build_chunk_specs_for_document(
                            document=document,
                            section_max_chars=self._section_max_chars,
                        )
                    )

            embedded_chunks, failed_chunks = await self._embedder.embed_chunk_specs(chunk_specs_to_embed)
            self._chunks = sorted(
                [*reused_chunks, *embedded_chunks],
                key=lambda chunk: (chunk.path, chunk.order, chunk.id),
            )
            self._updated_at = utc_now()
            self._file_signatures = current_signatures
            self._index_embedding_model = self._embedding_model
            self._index_section_max_chars = self._section_max_chars
            self._rebuild_indexes()
            self._write_index_to_disk()

            return {
                "indexed_files": len(documents),
                "indexed_chunks": len(self._chunks),
                "failed_chunks": failed_chunks,
                "updated_at": self._updated_at,
            }

    async def build_context_payload(self, query: str) -> RagContextPayload:
        context = await self.retrieve_context(query)
        if not context.entries:
            return RagContextPayload(
                context_message=None,
                sources=[],
                should_refuse=context.should_refuse,
                refusal_message=context.refusal_message,
            )

        blocks: list[str] = []
        for index, entry in enumerate(context.entries, start=1):
            blocks.append(
                "\n".join(
                    [
                        f"[Source {index}]",
                        f"path: {entry.source.path}",
                        f"heading: {entry.source.heading}",
                        "content:",
                        entry.content,
                    ]
                )
            )

        return RagContextPayload(
            context_message={
                "role": "system",
                "content": (
                    "Use the following Obsidian notes as references. "
                    "Answer only when the notes contain enough support, cite the source path you used, and never cite synthetic [Source N] labels.\n\n"
                    + "\n\n".join(blocks)
                ),
            },
            sources=[source.to_payload() for source in context.sources],
            should_refuse=context.should_refuse,
            refusal_message=context.refusal_message,
        )

    async def retrieve_context(self, query: str) -> ContextPayload:
        query_filters = parse_query_filters(query)
        if not query_filters.cleaned_query and not any(
            (query_filters.folders, query_filters.paths, query_filters.tags)
        ):
            return ContextPayload()
        if not self._vault_path.exists():
            return ContextPayload(
                should_refuse=True,
                refusal_message=self._missing_vault_message(query),
                debug={"rag_ready": False, "rag_reason": "vault_missing"},
            )
        if not self._chunks:
            return ContextPayload(
                should_refuse=True,
                refusal_message=self._empty_index_message(query),
                debug={"rag_ready": False, "rag_reason": "index_empty"},
            )

        candidates = await self._retrieve_candidates(query_filters)
        if not candidates:
            return ContextPayload(
                should_refuse=True,
                refusal_message=self._insufficient_support_message(query),
                debug={"rag_ready": True, "rag_reason": "no_candidates"},
            )

        primary_candidates = self._reranker.rerank(
            query=query_filters.cleaned_query,
            candidates=candidates,
        )[: self._top_k]
        if not primary_candidates or primary_candidates[0].final_score < self._min_score:
            return ContextPayload(
                should_refuse=True,
                refusal_message=self._insufficient_support_message(query),
                debug={"rag_ready": True, "rag_reason": "low_score"},
            )

        context_limit = max(self._top_k, self._top_k * (1 + self._neighbor_window * 2))
        context_chunks = expand_neighbor_chunks(
            primary_candidates=primary_candidates,
            chunks_by_path=self._chunks_by_path,
            neighbor_window=self._neighbor_window,
            limit=context_limit,
        )
        if not context_chunks:
            return ContextPayload(
                should_refuse=True,
                refusal_message=self._insufficient_support_message(query),
                debug={"rag_ready": True, "rag_reason": "no_context_chunks"},
            )

        sources = [
            SourceItem(
                type="note",
                path=candidate.chunk.path,
                heading=candidate.chunk.heading,
                excerpt=self._truncate_excerpt(candidate.chunk.content),
                score=candidate.final_score,
            )
            for candidate in primary_candidates
        ]

        scores_by_chunk_id = {candidate.chunk.id: candidate.final_score for candidate in primary_candidates}
        entries = [
            ContextEntry(
                source=SourceItem(
                    type="note",
                    path=chunk.path,
                    heading=chunk.heading,
                    excerpt=self._truncate_excerpt(chunk.content),
                    score=scores_by_chunk_id.get(chunk.id, 0.0),
                ),
                content=chunk.content,
            )
            for chunk in context_chunks
        ]
        return ContextPayload(
            entries=entries,
            sources=sources,
            debug={"rag_ready": True, "rag_reason": "ok"},
        )

    async def _retrieve_candidates(
        self, query_filters: QueryFilters
    ) -> list[RetrievalCandidate]:
        if not self._chunks or not query_filters.cleaned_query:
            return []

        query_embedding = await self._embedder.embed_query(query_filters.cleaned_query)
        return self._retriever.retrieve(
            query_filters=query_filters,
            query_embedding=query_embedding,
            top_k=self._top_k,
            candidate_limit=self._candidate_limit,
        )

    def _can_reuse_chunks(self) -> bool:
        return (
            bool(self._file_signatures)
            and self._index_embedding_model == self._embedding_model
            and self._index_section_max_chars == self._section_max_chars
        )

    def _truncate_excerpt(self, content: str, limit: int = 280) -> str:
        normalized = " ".join(content.split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit].rstrip()}..."

    def _missing_vault_message(self, query: str) -> str:
        if prefers_simplified_chinese(query):
            return "当前找不到配置的笔记目录，没法检索你的文档。先检查 RAG 目录配置。"
        return (
            "The configured notes directory could not be found, so I cannot search your documents. "
            "Check the RAG vault path first."
        )

    def _empty_index_message(self, query: str) -> str:
        if prefers_simplified_chinese(query):
            return "当前笔记索引还是空的，没法检索你的文档。先在设置里更新数据库，再试一次。"
        return (
            "The note index is still empty, so I cannot search your documents yet. "
            "Update the database first and try again."
        )

    def _insufficient_support_message(self, query: str) -> str:
        if prefers_simplified_chinese(query):
            return "我没能在你的笔记里找到足够依据来回答这个问题。可以换个问法，或者用 `folder:`、`tag:`、`path:` 缩小范围。"
        return (
            "I could not find enough support in your notes for this question. "
            "Try rephrasing it, or narrow the scope with folder:/tag:/path: filters."
        )

    def _load_index_from_disk(self) -> None:
        snapshot = self._store.load()
        self._chunks = snapshot.chunks
        self._updated_at = snapshot.updated_at
        self._index_embedding_model = snapshot.embedding_model
        self._index_section_max_chars = snapshot.section_max_chars
        self._file_signatures = snapshot.file_signatures
        self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        chunks_by_path: dict[str, list[RagChunk]] = {}
        for chunk in self._chunks:
            chunks_by_path.setdefault(chunk.path, []).append(chunk)

        for path, chunks in chunks_by_path.items():
            ordered_chunks = sorted(chunks, key=lambda item: item.order)
            for index, chunk in enumerate(ordered_chunks):
                chunk.order = index
            chunks_by_path[path] = ordered_chunks

        self._chunks_by_path = chunks_by_path
        self._chunks = [chunk for path in sorted(chunks_by_path) for chunk in chunks_by_path[path]]
        self._retriever.set_chunks(self._chunks)

    def _write_index_to_disk(self) -> None:
        self._store.write(
            updated_at=self._updated_at,
            embedding_model=self._embedding_model,
            section_max_chars=self._section_max_chars,
            file_signatures=self._file_signatures,
            chunks=self._chunks,
        )
