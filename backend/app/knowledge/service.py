from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session, selectinload

from ..core.config import Settings
from ..retrieval.language import prefers_simplified_chinese
from ..retrieval.rag.chunking import build_chunk_specs_for_document
from ..retrieval.rag.embedder import build_knowledge_embedder
from ..retrieval.rag.model_reranker import ModelReranker
from ..retrieval.rag.neighbors import expand_neighbor_chunks
from ..retrieval.rag.retriever import HybridRetriever
from ..retrieval.rag.types import MarkdownDocument, QueryFilters, RagChunk
from ..retrieval.types import ContextEntry, ContextPayload, SourceItem
from ..storage.database import SessionLocal
from ..storage.models import KnowledgeChunk, KnowledgeDocument


logger = logging.getLogger("chatchat.knowledge")


@dataclass(frozen=True)
class PendingKnowledgeUpload:
    title: str
    mime_type: str
    extension: str
    size_bytes: int
    sha1: str
    content: bytes


def _resolve_storage_root(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / raw_path
    path.mkdir(parents=True, exist_ok=True)
    return path


class KnowledgeService:
    def __init__(self, settings: Settings):
        self._storage_root = _resolve_storage_root(settings.knowledge_storage_root)
        self._max_file_size_bytes = max(1, settings.knowledge_max_file_size_bytes)
        self._max_documents_per_user = max(1, settings.knowledge_max_documents_per_user)
        self._max_total_size_bytes = max(self._max_file_size_bytes, settings.knowledge_max_total_size_bytes)
        self._top_k = max(1, settings.knowledge_top_k)
        self._section_max_chars = max(400, settings.knowledge_section_max_chars)
        self._candidate_limit = max(self._top_k, settings.knowledge_candidate_limit)
        self._rerank_window = max(self._top_k, settings.knowledge_rerank_window)
        self._neighbor_window = max(0, settings.knowledge_neighbor_window)
        self._min_score = max(0.0, settings.knowledge_min_score)
        self._embedder = build_knowledge_embedder(settings, settings.knowledge_embedding_model)
        self._retriever = HybridRetriever()
        self._reranker = ModelReranker(settings, rerank_window=self._rerank_window)
        self._reindex_tasks: dict[int, asyncio.Task[None]] = {}
        self._reindex_lock = asyncio.Lock()

    def list_documents(self, *, db: Session, user_id: int) -> list[KnowledgeDocument]:
        return list(
            db.scalars(
                select(KnowledgeDocument)
                .options(selectinload(KnowledgeDocument.chunks))
                .where(KnowledgeDocument.user_id == user_id)
                .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())
            ).all()
        )

    def status(self, *, db: Session, user_id: int) -> dict[str, int]:
        counts = db.execute(
            select(
                func.count(KnowledgeDocument.id),
                func.sum(case((KnowledgeDocument.status == "pending", 1), else_=0)),
                func.sum(case((KnowledgeDocument.status == "indexing", 1), else_=0)),
                func.sum(case((KnowledgeDocument.status == "ready", 1), else_=0)),
                func.sum(case((KnowledgeDocument.status == "failed", 1), else_=0)),
                func.sum(KnowledgeDocument.size_bytes),
            ).where(KnowledgeDocument.user_id == user_id)
        ).one()
        chunk_count = db.scalar(
            select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.user_id == user_id)
        ) or 0
        return {
            "document_count": int(counts[0] or 0),
            "pending_document_count": int(counts[1] or 0),
            "indexing_document_count": int(counts[2] or 0),
            "ready_document_count": int(counts[3] or 0),
            "failed_document_count": int(counts[4] or 0),
            "chunk_count": int(chunk_count),
            "total_size_bytes": int(counts[5] or 0),
            "max_documents_per_user": self._max_documents_per_user,
            "max_total_size_bytes": self._max_total_size_bytes,
            "max_file_size_bytes": self._max_file_size_bytes,
        }

    async def create_document(
        self,
        *,
        db: Session,
        user_id: int,
        upload: UploadFile,
    ) -> KnowledgeDocument:
        return (await self.create_documents(db=db, user_id=user_id, uploads=[upload]))[0]

    async def create_documents(
        self,
        *,
        db: Session,
        user_id: int,
        uploads: list[UploadFile],
    ) -> list[KnowledgeDocument]:
        pending_uploads = [await self._read_upload(upload) for upload in uploads]
        self._validate_upload_batch(db=db, user_id=user_id, pending_uploads=pending_uploads)

        created_documents: list[KnowledgeDocument] = []
        written_paths: list[Path] = []
        try:
            for pending in pending_uploads:
                document = KnowledgeDocument(
                    user_id=user_id,
                    title=pending.title,
                    mime_type=pending.mime_type,
                    extension=pending.extension,
                    size_bytes=pending.size_bytes,
                    relative_path="",
                    sha1=pending.sha1,
                    status="pending",
                    error_message=None,
                )
                db.add(document)
                db.flush()

                relative_path = Path(str(user_id)) / f"{document.id}{pending.extension}"
                file_path = self._storage_root / relative_path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(pending.content)
                written_paths.append(file_path)

                document.relative_path = relative_path.as_posix()
                db.add(document)
                created_documents.append(document)

            db.commit()
        except Exception:
            db.rollback()
            for file_path in written_paths:
                if file_path.exists():
                    file_path.unlink()
            raise

        for document in created_documents:
            db.refresh(document)
        return created_documents

    async def reindex_document(
        self,
        *,
        db: Session,
        user_id: int,
        document_id: int,
    ) -> KnowledgeDocument | None:
        document = db.scalar(
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.id == document_id,
                KnowledgeDocument.user_id == user_id,
            )
        )
        if document is None:
            return None

        file_path = self._storage_root / Path(document.relative_path)
        if not file_path.exists():
            return self._mark_document_failed(
                db=db,
                document=document,
                error_message="Markdown file is missing from storage.",
            )

        async with self._reindex_lock:
            if self._user_has_active_reindex_task(user_id):
                db.refresh(document)
                return document

            self._mark_document_indexing(db=db, document=document)
            task = asyncio.create_task(self._run_reindex_documents(user_id=user_id, document_ids=[document.id]))
            self._register_reindex_task(user_id=user_id, task=task)
            db.refresh(document)
            return document

    async def reindex_pending_documents(
        self,
        *,
        db: Session,
        user_id: int,
    ) -> dict[str, int]:
        async with self._reindex_lock:
            if self._user_has_active_reindex_task(user_id):
                status = self.status(db=db, user_id=user_id)
                return self._build_reindex_result(
                    started=False,
                    scheduled_documents=0,
                    status=status,
                )

            documents = list(
                db.scalars(
                    select(KnowledgeDocument)
                    .where(
                        KnowledgeDocument.user_id == user_id,
                        KnowledgeDocument.status.in_(("pending", "failed")),
                    )
                    .order_by(KnowledgeDocument.id.asc())
                ).all()
            )
            if not documents:
                status = self.status(db=db, user_id=user_id)
                return self._build_reindex_result(
                    started=False,
                    scheduled_documents=0,
                    status=status,
                )

            document_ids = [document.id for document in documents]
            for document in documents:
                self._mark_document_indexing(db=db, document=document, commit=False)
            db.commit()

            task = asyncio.create_task(self._run_reindex_documents(user_id=user_id, document_ids=document_ids))
            self._register_reindex_task(user_id=user_id, task=task)

            status = self.status(db=db, user_id=user_id)
            return self._build_reindex_result(
                started=True,
                scheduled_documents=len(document_ids),
                status=status,
            )

    def _build_reindex_result(
        self,
        *,
        started: bool,
        scheduled_documents: int,
        status: dict[str, int],
    ) -> dict[str, int | bool]:
        return {
            "started": started,
            "scheduled_documents": scheduled_documents,
            "indexing_documents": status["indexing_document_count"],
            "ready_documents": status["ready_document_count"],
            "failed_documents": status["failed_document_count"],
            "chunk_count": status["chunk_count"],
        }

    def _user_has_active_reindex_task(self, user_id: int) -> bool:
        task = self._reindex_tasks.get(user_id)
        return task is not None and not task.done()

    def _register_reindex_task(self, *, user_id: int, task: asyncio.Task[None]) -> None:
        self._reindex_tasks[user_id] = task
        task.add_done_callback(lambda completed_task: self._finalize_reindex_task(user_id=user_id, task=completed_task))

    def _finalize_reindex_task(self, *, user_id: int, task: asyncio.Task[None]) -> None:
        current_task = self._reindex_tasks.get(user_id)
        if current_task is task:
            self._reindex_tasks.pop(user_id, None)
        try:
            task.result()
        except Exception:
            logger.exception("knowledge reindex task failed | user_id=%s", user_id)

    async def _run_reindex_documents(self, *, user_id: int, document_ids: list[int]) -> None:
        for document_id in document_ids:
            with SessionLocal() as db:
                document = db.scalar(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.id == document_id,
                        KnowledgeDocument.user_id == user_id,
                    )
                )
                if document is None:
                    continue

                file_path = self._storage_root / Path(document.relative_path)
                if not file_path.exists():
                    self._mark_document_failed(
                        db=db,
                        document=document,
                        error_message="Markdown file is missing from storage.",
                    )
                    continue

                try:
                    await self._index_document(
                        db=db,
                        document=document,
                        content=file_path.read_text(encoding="utf-8", errors="ignore"),
                    )
                except Exception as exc:
                    self._mark_document_failed(
                        db=db,
                        document=document,
                        error_message=str(exc).strip() or exc.__class__.__name__,
                    )

    def delete_document(self, *, db: Session, user_id: int, document_id: int) -> str | None:
        deleted_ids, relative_paths = self.delete_documents(db=db, user_id=user_id, document_ids=[document_id])
        return relative_paths[0] if deleted_ids else None

    def delete_documents(self, *, db: Session, user_id: int, document_ids: list[int]) -> tuple[list[int], list[str]]:
        normalized_ids = [document_id for document_id in dict.fromkeys(document_ids) if isinstance(document_id, int)]
        if not normalized_ids:
            return [], []

        documents = list(
            db.scalars(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.user_id == user_id,
                    KnowledgeDocument.id.in_(normalized_ids),
                )
            ).all()
        )
        if not documents:
            return [], []

        deleted_ids = [document.id for document in documents]
        relative_paths = [document.relative_path for document in documents if document.relative_path]
        for document in documents:
            db.delete(document)
        db.commit()
        return deleted_ids, relative_paths

    def remove_files(self, relative_paths: list[str]) -> None:
        for relative_path in relative_paths:
            self.remove_file(relative_path)

    async def _read_upload(self, upload: UploadFile) -> PendingKnowledgeUpload:
        filename = (upload.filename or "").strip()
        extension = Path(filename).suffix.lower()
        content = await upload.read()
        await upload.close()

        if extension != ".md":
            raise ValueError("Only Markdown files (.md) are supported.")
        if not content:
            raise ValueError("Uploaded Markdown file is empty.")
        if len(content) > self._max_file_size_bytes:
            raise ValueError(
                f"Markdown files must be {self._max_file_size_bytes // (1024 * 1024)} MB or smaller."
            )

        title = filename or "document.md"
        return PendingKnowledgeUpload(
            title=title,
            mime_type=(upload.content_type or "text/markdown").strip() or "text/markdown",
            extension=extension,
            size_bytes=len(content),
            sha1=hashlib.sha1(content).hexdigest(),
            content=content,
        )

    def _validate_upload_batch(
        self,
        *,
        db: Session,
        user_id: int,
        pending_uploads: list[PendingKnowledgeUpload],
    ) -> None:
        if not pending_uploads:
            raise ValueError("Select at least one Markdown file.")

        titles = [upload.title for upload in pending_uploads]
        if len(titles) != len(set(titles)):
            raise ValueError("Batch upload contains duplicate filenames.")

        document_count, total_size_bytes = db.execute(
            select(
                func.count(KnowledgeDocument.id),
                func.sum(KnowledgeDocument.size_bytes),
            ).where(KnowledgeDocument.user_id == user_id)
        ).one()
        next_document_count = int(document_count or 0) + len(pending_uploads)
        next_total_size = int(total_size_bytes or 0) + sum(upload.size_bytes for upload in pending_uploads)
        if next_document_count > self._max_documents_per_user:
            raise ValueError(f"You can upload up to {self._max_documents_per_user} Markdown documents.")
        if next_total_size > self._max_total_size_bytes:
            raise ValueError("Uploading these files would exceed your knowledge storage limit.")

        existing_titles = set(
            db.scalars(
                select(KnowledgeDocument.title).where(
                    KnowledgeDocument.user_id == user_id,
                    KnowledgeDocument.title.in_(titles),
                )
            ).all()
        )
        if existing_titles:
            duplicated = sorted(existing_titles)
            raise ValueError(
                "These Markdown filenames already exist: " + ", ".join(duplicated)
            )

    def remove_file(self, relative_path: str | None) -> None:
        if not relative_path:
            return
        file_path = self._storage_root / Path(relative_path)
        if file_path.exists():
            file_path.unlink()

    async def retrieve_context(
        self,
        *,
        db: Session,
        user_id: int,
        query: str,
    ) -> ContextPayload:
        cleaned_query = query.strip()
        if not cleaned_query:
            return ContextPayload()

        documents = self.list_documents(db=db, user_id=user_id)
        ready_documents = [document for document in documents if document.status == "ready"]
        if not ready_documents:
            return ContextPayload(
                should_refuse=True,
                refusal_message=self._missing_documents_message(query),
                debug={"rag_ready": False, "rag_reason": "no_ready_documents"},
            )

        chunks = self._build_runtime_chunks(ready_documents)
        if not chunks:
            return ContextPayload(
                should_refuse=True,
                refusal_message=self._missing_documents_message(query),
                debug={"rag_ready": False, "rag_reason": "no_chunks"},
            )

        self._retriever.set_chunks(chunks)
        query_embedding = await self._embedder.embed_query(cleaned_query)
        candidates = self._retriever.retrieve(
            query_filters=QueryFilters(cleaned_query=cleaned_query),
            query_embedding=query_embedding,
            top_k=self._top_k,
            candidate_limit=self._candidate_limit,
        )
        if not candidates:
            return ContextPayload(
                should_refuse=True,
                refusal_message=self._insufficient_support_message(query),
                debug={"rag_ready": True, "rag_reason": "no_candidates"},
            )

        primary_candidates = (
            await self._reranker.rerank(
                query=cleaned_query,
                candidates=candidates,
            )
        )[: self._top_k]
        if not primary_candidates or primary_candidates[0].final_score < self._min_score:
            return ContextPayload(
                should_refuse=True,
                refusal_message=self._insufficient_support_message(query),
                debug={"rag_ready": True, "rag_reason": "low_score"},
            )

        chunks_by_path: dict[str, list[RagChunk]] = {}
        for chunk in chunks:
            chunks_by_path.setdefault(chunk.path, []).append(chunk)
        context_limit = max(self._top_k, self._top_k * (1 + self._neighbor_window * 2))
        context_chunks = expand_neighbor_chunks(
            primary_candidates=primary_candidates,
            chunks_by_path=chunks_by_path,
            neighbor_window=self._neighbor_window,
            limit=context_limit,
        )
        if not context_chunks:
            return ContextPayload(
                should_refuse=True,
                refusal_message=self._insufficient_support_message(query),
                debug={"rag_ready": True, "rag_reason": "no_context_chunks"},
            )

        scores_by_chunk_key = {candidate.chunk.id: candidate.final_score for candidate in primary_candidates}
        sources = [
            SourceItem(
                type="note",
                path=candidate.chunk.path,
                heading=candidate.chunk.heading,
                excerpt=self._truncate_excerpt(candidate.chunk.content),
                score=candidate.final_score,
                title=candidate.chunk.path,
            )
            for candidate in primary_candidates
        ]
        entries = [
            ContextEntry(
                source=SourceItem(
                    type="note",
                    path=chunk.path,
                    heading=chunk.heading,
                    excerpt=self._truncate_excerpt(chunk.content),
                    score=scores_by_chunk_key.get(chunk.id, 0.0),
                    title=chunk.path,
                ),
                content=chunk.content,
            )
            for chunk in context_chunks
        ]
        return ContextPayload(
            entries=entries,
            sources=sources,
            debug={
                "rag_ready": True,
                "rag_reason": "ok",
                "knowledge_ready_documents": len(ready_documents),
                "knowledge_total_documents": len(documents),
                "knowledge_chunk_count": len(chunks),
                "knowledge_rerank_enabled": self._reranker.enabled,
                "knowledge_rerank_reason": self._reranker.disabled_reason or "active",
            },
        )

    async def _index_document(
        self,
        *,
        db: Session,
        document: KnowledgeDocument,
        content: str,
    ) -> KnowledgeDocument:
        markdown_document = MarkdownDocument(
            path=document.title,
            content=content,
            signature=document.sha1,
        )
        chunk_specs = build_chunk_specs_for_document(
            document=markdown_document,
            section_max_chars=self._section_max_chars,
        )

        if not chunk_specs:
            return self._mark_document_failed(
                db=db,
                document=document,
                error_message="Markdown file did not produce any searchable sections.",
            )

        try:
            embedded_chunks, failed_chunks = await self._embedder.embed_chunk_specs(chunk_specs)
        except Exception as exc:
            return self._mark_document_failed(
                db=db,
                document=document,
                error_message=str(exc).strip() or exc.__class__.__name__,
            )

        if failed_chunks or not embedded_chunks:
            return self._mark_document_failed(
                db=db,
                document=document,
                error_message="Embedding generation failed for one or more knowledge chunks.",
            )

        db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))

        for chunk in embedded_chunks:
            db.add(
                KnowledgeChunk(
                    document_id=document.id,
                    user_id=document.user_id,
                    chunk_key=chunk.id,
                    chunk_index=chunk.order,
                    path=chunk.path,
                    directory=chunk.directory,
                    heading=chunk.heading,
                    content=chunk.content,
                    token_count=max(1, len(chunk.content) // 4),
                    tags_json=json.dumps(chunk.tags, ensure_ascii=False),
                    embedding_json=json.dumps(chunk.embedding),
                )
            )

        document.status = "ready"
        document.error_message = None
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    def _mark_document_indexing(self, *, db: Session, document: KnowledgeDocument, commit: bool = True) -> None:
        document.status = "indexing"
        document.error_message = None
        db.add(document)
        if commit:
            db.commit()

    def _mark_document_failed(
        self,
        *,
        db: Session,
        document: KnowledgeDocument,
        error_message: str,
    ) -> KnowledgeDocument:
        document.status = "failed"
        document.error_message = error_message
        db.add(document)
        db.commit()
        db.refresh(document)
        return document

    def _build_runtime_chunks(self, documents: list[KnowledgeDocument]) -> list[RagChunk]:
        chunks: list[RagChunk] = []
        for document in documents:
            for chunk in document.chunks:
                chunks.append(
                    RagChunk(
                        id=chunk.chunk_key,
                        path=chunk.path,
                        directory=chunk.directory,
                        heading=chunk.heading,
                        content=chunk.content,
                        order=chunk.chunk_index,
                        embedding=chunk.embedding,
                        tags=chunk.tags,
                    )
                )
        return sorted(chunks, key=lambda item: (item.path, item.order, item.id))

    def _truncate_excerpt(self, content: str, limit: int = 280) -> str:
        normalized = " ".join(content.split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit].rstrip()}..."

    def _missing_documents_message(self, query: str) -> str:
        if prefers_simplified_chinese(query):
            return "当前还没有可用的知识文档。先上传 Markdown 文档，再使用知识库检索。"
        return "No ready knowledge documents are available yet. Upload Markdown files before using RAG."

    def _insufficient_support_message(self, query: str) -> str:
        if prefers_simplified_chinese(query):
            return "我没能在你的知识文档里找到足够依据来回答这个问题。可以换个问法，或者补充更多 Markdown 文档。"
        return (
            "I could not find enough support in your knowledge documents for this question. "
            "Try rephrasing it or upload more Markdown files."
        )
