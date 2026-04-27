from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import and_, case, delete, func, literal_column, or_, select
from sqlalchemy.orm import Session, selectinload

from ..core.config import Settings
from ..retrieval.language import prefers_simplified_chinese
from ..retrieval.rag.chunking import build_chunk_specs_for_document
from ..retrieval.rag.embedder import build_knowledge_embedder
from ..retrieval.rag.model_reranker import ModelReranker
from ..retrieval.rag.neighbors import expand_neighbor_chunks
from ..retrieval.rag.query_filters import chunk_matches_filters, parse_query_filters
from ..retrieval.rag.retriever import HybridRetriever
from ..retrieval.rag.text import normalize_path_fragment, tokenize_text
from ..retrieval.rag.types import MarkdownDocument, QueryFilters, RagChunk, RetrievalCandidate
from ..retrieval.types import ContextEntry, ContextPayload, SourceItem
from ..storage.database import SessionLocal
from ..storage.models import KnowledgeChunk, KnowledgeDocument, KnowledgeFolder


logger = logging.getLogger("chatchat.knowledge")


@dataclass(frozen=True)
class PendingKnowledgeUpload:
    title: str
    folder: str
    path: str
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
        self._vector_weight = getattr(self._retriever, "_vector_weight", 0.72)
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

    def list_folders(self, *, db: Session, user_id: int) -> list[str]:
        saved_folders = set(
            db.scalars(
                select(KnowledgeFolder.name).where(KnowledgeFolder.user_id == user_id)
            ).all()
        )
        document_folders = set(
            db.scalars(
                select(KnowledgeDocument.folder).where(
                    KnowledgeDocument.user_id == user_id,
                    KnowledgeDocument.folder != "",
                )
            ).all()
        )
        return sorted(
            folder for folder in saved_folders.union(document_folders) if folder
        )

    def create_folder(self, *, db: Session, user_id: int, name: str) -> str:
        folder = self._sanitize_folder(name)
        if not folder:
            raise ValueError("Folder name is required.")
        if len(folder) > 255:
            raise ValueError("Folder names must be 255 characters or shorter.")
        self._ensure_folder(db=db, user_id=user_id, folder=folder, commit=True)
        return folder

    def delete_folder(self, *, db: Session, user_id: int, name: str) -> dict[str, int | str] | None:
        folder = self._sanitize_folder(name)
        if not folder:
            raise ValueError("Default folder cannot be deleted.")

        folder_model = db.scalar(
            select(KnowledgeFolder).where(
                KnowledgeFolder.user_id == user_id,
                KnowledgeFolder.name == folder,
            )
        )
        documents = list(
            db.scalars(
                select(KnowledgeDocument)
                .options(selectinload(KnowledgeDocument.chunks))
                .where(
                    KnowledgeDocument.user_id == user_id,
                    KnowledgeDocument.folder == folder,
                )
                .order_by(KnowledgeDocument.id.asc())
            ).all()
        )
        if folder_model is None and not documents:
            return None

        moving_titles = [document.title for document in documents]
        if len(moving_titles) != len(set(moving_titles)):
            raise ValueError("Deleting this folder would create duplicate document names in the default group.")
        existing_default_titles = set(
            db.scalars(
                select(KnowledgeDocument.title).where(
                    KnowledgeDocument.user_id == user_id,
                    KnowledgeDocument.folder == "",
                    KnowledgeDocument.title.in_(moving_titles),
                )
            ).all()
        )
        if existing_default_titles:
            raise ValueError(
                "Deleting this folder would create duplicate paths in the default group: "
                + ", ".join(sorted(existing_default_titles))
            )

        for document in documents:
            document.folder = ""
            db.add(document)
            for chunk in document.chunks:
                chunk.path = document.path
                chunk.directory = ""
                db.add(chunk)
        if folder_model is not None:
            db.delete(folder_model)
        db.commit()
        return {
            "folder": folder,
            "moved_document_count": len(documents),
        }

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
        folder: str = "",
        relative_path: str = "",
    ) -> KnowledgeDocument:
        return (
            await self.create_documents(
                db=db,
                user_id=user_id,
                uploads=[upload],
                folder=folder,
                relative_paths=[relative_path] if relative_path else [],
            )
        )[0]

    async def create_documents(
        self,
        *,
        db: Session,
        user_id: int,
        uploads: list[UploadFile],
        folder: str = "",
        relative_paths: list[str] | None = None,
    ) -> list[KnowledgeDocument]:
        paths = relative_paths or []
        pending_uploads = [
            await self._read_upload(
                upload,
                folder=folder,
                relative_path=paths[index] if index < len(paths) else "",
            )
            for index, upload in enumerate(uploads)
        ]
        self._validate_upload_batch(db=db, user_id=user_id, pending_uploads=pending_uploads)

        created_documents: list[KnowledgeDocument] = []
        written_paths: list[Path] = []
        try:
            for folder_name in dict.fromkeys(pending.folder for pending in pending_uploads if pending.folder):
                self._ensure_folder(db=db, user_id=user_id, folder=folder_name)
            for pending in pending_uploads:
                document = KnowledgeDocument(
                    user_id=user_id,
                    title=pending.title,
                    folder=pending.folder,
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
            try:
                indexed = await self._index_document(
                    db=db,
                    document=document,
                    content=file_path.read_text(encoding="utf-8", errors="ignore"),
                )
            except Exception as exc:
                indexed = self._mark_document_failed(
                    db=db,
                    document=document,
                    error_message=str(exc).strip() or exc.__class__.__name__,
                )
            db.refresh(indexed)
            return indexed

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

    def move_documents(
        self,
        *,
        db: Session,
        user_id: int,
        document_ids: list[int],
        folder: str,
    ) -> list[KnowledgeDocument]:
        normalized_ids = [document_id for document_id in dict.fromkeys(document_ids) if isinstance(document_id, int)]
        if not normalized_ids:
            return []

        target_folder = self._sanitize_folder(folder)
        documents = list(
            db.scalars(
                select(KnowledgeDocument)
                .options(selectinload(KnowledgeDocument.chunks))
                .where(
                    KnowledgeDocument.user_id == user_id,
                    KnowledgeDocument.id.in_(normalized_ids),
                )
                .order_by(KnowledgeDocument.id.asc())
            ).all()
        )
        if not documents:
            return []

        target_paths = [
            self._document_path_for(folder=target_folder, title=document.title)
            for document in documents
        ]
        if len(target_paths) != len(set(target_paths)):
            raise ValueError("Moving these documents would create duplicate paths.")

        existing_documents = list(
            db.scalars(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.user_id == user_id,
                    KnowledgeDocument.id.notin_([document.id for document in documents]),
                )
            ).all()
        )
        existing_paths = {document.path for document in existing_documents}
        duplicated = sorted(path for path in target_paths if path in existing_paths)
        if duplicated:
            raise ValueError("These knowledge paths already exist: " + ", ".join(duplicated))

        for document in documents:
            document.folder = target_folder
            db.add(document)
            for chunk in document.chunks:
                chunk.path = document.path
                chunk.directory = target_folder
                db.add(chunk)
        self._ensure_folder(db=db, user_id=user_id, folder=target_folder)

        db.commit()
        for document in documents:
            db.refresh(document)
        return documents

    def _document_path_for(self, *, folder: str, title: str) -> str:
        path = f"{folder}/{title}" if folder else title
        if len(path) > 255:
            raise ValueError("Knowledge document paths must be 255 characters or shorter.")
        return path

    def remove_files(self, relative_paths: list[str]) -> None:
        for relative_path in relative_paths:
            self.remove_file(relative_path)

    async def _read_upload(
        self,
        upload: UploadFile,
        *,
        folder: str,
        relative_path: str,
    ) -> PendingKnowledgeUpload:
        filename = (upload.filename or "").strip()
        upload_path = self._resolve_upload_path(filename=filename, folder=folder, relative_path=relative_path)
        extension = Path(upload_path).suffix.lower()
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

        title = Path(upload_path).name or "document.md"
        document_folder = upload_path.rsplit("/", 1)[0] if "/" in upload_path else ""
        return PendingKnowledgeUpload(
            title=title,
            folder=document_folder,
            path=upload_path,
            mime_type=(upload.content_type or "text/markdown").strip() or "text/markdown",
            extension=extension,
            size_bytes=len(content),
            sha1=hashlib.sha1(content).hexdigest(),
            content=content,
        )

    def _resolve_upload_path(self, *, filename: str, folder: str, relative_path: str) -> str:
        base_folder = self._sanitize_folder(folder)
        candidate = self._sanitize_relative_path(relative_path) or self._sanitize_relative_path(filename)
        if not candidate:
            candidate = "document.md"
        if base_folder:
            candidate = f"{base_folder}/{candidate}"
        if len(candidate) > 255:
            raise ValueError("Knowledge document paths must be 255 characters or shorter.")
        return candidate

    def _sanitize_folder(self, value: str) -> str:
        return self._sanitize_relative_path(value)

    def _ensure_folder(
        self,
        *,
        db: Session,
        user_id: int,
        folder: str,
        commit: bool = False,
    ) -> KnowledgeFolder | None:
        folder_name = self._sanitize_folder(folder)
        if not folder_name:
            return None
        existing = db.scalar(
            select(KnowledgeFolder).where(
                KnowledgeFolder.user_id == user_id,
                KnowledgeFolder.name == folder_name,
            )
        )
        if existing is not None:
            return existing
        knowledge_folder = KnowledgeFolder(user_id=user_id, name=folder_name)
        db.add(knowledge_folder)
        if commit:
            db.commit()
            db.refresh(knowledge_folder)
        else:
            db.flush()
        return knowledge_folder

    def _sanitize_relative_path(self, value: str) -> str:
        raw_parts = str(value or "").replace("\\", "/").split("/")
        parts: list[str] = []
        for raw_part in raw_parts:
            part = raw_part.strip()
            if not part or part in {".", ".."}:
                continue
            parts.append(part[:255])
        return "/".join(parts).strip("/")

    def _validate_upload_batch(
        self,
        *,
        db: Session,
        user_id: int,
        pending_uploads: list[PendingKnowledgeUpload],
    ) -> None:
        if not pending_uploads:
            raise ValueError("Select at least one Markdown file.")

        paths = [upload.path for upload in pending_uploads]
        if len(paths) != len(set(paths)):
            raise ValueError("Batch upload contains duplicate knowledge paths.")

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

        existing_documents = list(
            db.scalars(
                select(KnowledgeDocument).where(KnowledgeDocument.user_id == user_id)
            ).all()
        )
        existing_paths = {document.path for document in existing_documents}
        duplicated = sorted(path for path in paths if path in existing_paths)
        if duplicated:
            raise ValueError(
                "These Markdown knowledge paths already exist: " + ", ".join(duplicated)
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
        folders: list[str] | None = None,
    ) -> ContextPayload:
        cleaned_query = query.strip()
        if not cleaned_query:
            return ContextPayload()
        query_filters = self._merge_scope_filters(parse_query_filters(cleaned_query), folders or [])
        retrieval_query = query_filters.cleaned_query or cleaned_query

        documents = self.list_documents(db=db, user_id=user_id)
        ready_documents = [document for document in documents if document.status == "ready"]
        if not ready_documents:
            return ContextPayload(
                should_refuse=True,
                refusal_message=self._missing_documents_message(query),
                debug={"rag_ready": False, "rag_reason": "no_ready_documents"},
            )

        query_embedding = await self._embedder.embed_query(retrieval_query)
        using_postgres = db.bind is not None and db.bind.dialect.name == "postgresql"
        candidate_chunks: list[RagChunk]
        context_chunk_pool: list[RagChunk]
        if using_postgres:
            candidates = self._retrieve_postgres_candidates(
                db=db,
                user_id=user_id,
                query_filters=query_filters,
                query_embedding=query_embedding,
            )
            candidate_chunks = [candidate.chunk for candidate in candidates]
            context_chunk_pool = []
        else:
            candidate_chunks = self._build_runtime_chunks(ready_documents)
            if not candidate_chunks:
                return ContextPayload(
                    should_refuse=True,
                    refusal_message=self._missing_documents_message(query),
                    debug={"rag_ready": False, "rag_reason": "no_chunks"},
                )
            self._retriever.set_chunks(candidate_chunks)
            candidates = self._retriever.retrieve(
                query_filters=query_filters,
                query_embedding=query_embedding,
                top_k=self._top_k,
                candidate_limit=self._candidate_limit,
            )
            context_chunk_pool = candidate_chunks
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

        context_limit = max(self._top_k, self._top_k * (1 + self._neighbor_window * 2))
        if using_postgres:
            context_chunk_pool = self._load_postgres_context_chunk_pool(
                db=db,
                user_id=user_id,
                primary_candidates=primary_candidates,
                limit=context_limit,
            )

        chunks_by_path: dict[str, list[RagChunk]] = {}
        for chunk in context_chunk_pool:
            chunks_by_path.setdefault(chunk.path, []).append(chunk)
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
                "rag_backend": "pgvector" if using_postgres else "hybrid_in_memory",
                "knowledge_ready_documents": len(ready_documents),
                "knowledge_total_documents": len(documents),
                "knowledge_candidate_count": len(candidates),
                "knowledge_context_chunk_count": len(context_chunk_pool),
                "knowledge_rerank_enabled": self._reranker.enabled,
                "knowledge_rerank_reason": self._reranker.disabled_reason or "active",
                "knowledge_scope_folders": list(query_filters.folders),
            },
        )

    def _merge_scope_filters(self, query_filters: QueryFilters, folders: list[str]) -> QueryFilters:
        normalized_folders: list[str] = []
        for folder in folders:
            raw_folder = str(folder).strip()
            normalized = "" if raw_folder == "__root__" else normalize_path_fragment(folder)
            if normalized or raw_folder in {"", "__root__"}:
                normalized_folders.append(normalized)
        merged_folders = tuple(dict.fromkeys([*query_filters.folders, *normalized_folders]))
        return QueryFilters(
            cleaned_query=query_filters.cleaned_query,
            folders=merged_folders,
            paths=query_filters.paths,
            tags=query_filters.tags,
        )

    async def _index_document(
        self,
        *,
        db: Session,
        document: KnowledgeDocument,
        content: str,
    ) -> KnowledgeDocument:
        markdown_document = MarkdownDocument(
            path=document.path,
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
                    embedding=chunk.embedding,
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
                chunks.append(self._runtime_chunk_from_model(chunk))
        return sorted(chunks, key=lambda item: (item.path, item.order, item.id))

    def _retrieve_postgres_candidates(
        self,
        *,
        db: Session,
        user_id: int,
        query_filters: QueryFilters,
        query_embedding: list[float],
    ) -> list[RetrievalCandidate]:
        filter_clauses = self._build_postgres_filter_clauses(user_id=user_id, query_filters=query_filters)
        distance_expr = KnowledgeChunk.embedding.cosine_distance(query_embedding)
        vector_rows = db.execute(
            select(KnowledgeChunk, distance_expr.label("distance"))
            .where(*filter_clauses)
            .order_by(distance_expr.asc(), KnowledgeChunk.chunk_index.asc(), KnowledgeChunk.id.asc())
            .limit(self._candidate_limit)
        ).all()

        keyword_terms = self._keyword_terms(query_filters.cleaned_query)
        keyword_rows: list[tuple[KnowledgeChunk, float]] = []
        if keyword_terms:
            search_text_expr = self._knowledge_search_text_expr()
            keyword_match_clauses = [
                search_text_expr.like(self._like_pattern(term), escape="\\")
                for term in keyword_terms
            ]
            keyword_score_expr = case((keyword_match_clauses[0], 1.0), else_=0.0)
            for clause in keyword_match_clauses[1:]:
                keyword_score_expr = keyword_score_expr + case((clause, 1.0), else_=0.0)
            keyword_score_expr = (keyword_score_expr / len(keyword_terms)).label("keyword_score")

            keyword_rows = [
                (chunk, float(score or 0.0))
                for chunk, score in db.execute(
                    select(KnowledgeChunk, keyword_score_expr)
                    .where(*filter_clauses, or_(*keyword_match_clauses))
                    .order_by(keyword_score_expr.desc(), KnowledgeChunk.chunk_index.asc(), KnowledgeChunk.id.asc())
                    .limit(self._candidate_limit)
                ).all()
            ]

        merged_rows: dict[int, dict[str, object]] = {}

        for chunk, distance in vector_rows:
            merged_rows[chunk.id] = {
                "chunk": chunk,
                "vector_raw": max(0.0, 1.0 - float(distance or 1.0)),
                "keyword_raw": 0.0,
            }

        for chunk, keyword_score in keyword_rows:
            item = merged_rows.setdefault(
                chunk.id,
                {
                    "chunk": chunk,
                    "vector_raw": 0.0,
                    "keyword_raw": 0.0,
                },
            )
            item["keyword_raw"] = max(float(item["keyword_raw"]), keyword_score)

        merged_items = list(merged_rows.values())
        vector_scores = self._min_max_normalize([float(item["vector_raw"]) for item in merged_items])
        keyword_scores = self._min_max_normalize([float(item["keyword_raw"]) for item in merged_items])

        candidates: list[RetrievalCandidate] = []
        for index, item in enumerate(merged_items):
            runtime_chunk = self._runtime_chunk_from_model(item["chunk"])
            if not runtime_chunk.embedding or not chunk_matches_filters(runtime_chunk, query_filters):
                continue
            hybrid_score = (
                self._vector_weight * vector_scores[index]
                + (1.0 - self._vector_weight) * keyword_scores[index]
            )
            candidates.append(
                RetrievalCandidate(
                    chunk=runtime_chunk,
                    vector_score=vector_scores[index],
                    keyword_score=keyword_scores[index],
                    hybrid_score=hybrid_score,
                    final_score=hybrid_score,
                )
            )
        candidates.sort(key=lambda item: item.hybrid_score, reverse=True)
        return candidates[: self._candidate_limit]

    def _load_postgres_context_chunk_pool(
        self,
        *,
        db: Session,
        user_id: int,
        primary_candidates: list[RetrievalCandidate],
        limit: int,
    ) -> list[RagChunk]:
        if self._neighbor_window <= 0:
            return [candidate.chunk for candidate in primary_candidates[:limit]]

        path_windows: dict[str, set[int]] = {}
        for candidate in primary_candidates:
            indices = path_windows.setdefault(candidate.chunk.path, set())
            for offset in range(-self._neighbor_window, self._neighbor_window + 1):
                sibling_index = candidate.chunk.order + offset
                if sibling_index >= 0:
                    indices.add(sibling_index)

        if not path_windows:
            return []

        window_clauses = [
            and_(
                KnowledgeChunk.path == path,
                KnowledgeChunk.chunk_index.in_(sorted(indices)),
            )
            for path, indices in path_windows.items()
            if indices
        ]
        if not window_clauses:
            return []

        rows = db.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.user_id == user_id, or_(*window_clauses))
            .order_by(KnowledgeChunk.path.asc(), KnowledgeChunk.chunk_index.asc(), KnowledgeChunk.id.asc())
        ).all()
        return [self._runtime_chunk_from_model(chunk) for chunk in rows]

    def _runtime_chunk_from_model(self, chunk: KnowledgeChunk) -> RagChunk:
        embedding = list(chunk.embedding) if chunk.embedding is not None else []
        return RagChunk(
            id=chunk.chunk_key,
            path=chunk.path,
            directory=chunk.directory,
            heading=chunk.heading,
            content=chunk.content,
            order=chunk.chunk_index,
            embedding=embedding,
            tags=chunk.tags,
        )

    def _build_postgres_filter_clauses(
        self,
        *,
        user_id: int,
        query_filters: QueryFilters,
    ) -> list[object]:
        clauses: list[object] = [KnowledgeChunk.user_id == user_id]
        lower_path = func.lower(KnowledgeChunk.path)
        lower_directory = func.lower(KnowledgeChunk.directory)
        lower_tags = func.lower(KnowledgeChunk.tags_json)

        if query_filters.folders:
            folder_clauses = []
            for folder in query_filters.folders:
                if folder == "":
                    folder_clauses.append(lower_directory == "")
                    continue
                folder_clauses.append(
                    or_(
                        lower_directory == folder,
                        lower_directory.like(self._folder_prefix_pattern(folder), escape="\\"),
                    )
                )
            clauses.append(
                or_(*folder_clauses)
            )

        if query_filters.paths:
            clauses.append(
                or_(
                    *[
                        lower_path.like(self._like_pattern(path), escape="\\")
                        for path in query_filters.paths
                    ]
                )
            )

        if query_filters.tags:
            for tag in query_filters.tags:
                clauses.append(lower_tags.like(self._json_tag_pattern(tag), escape="\\"))

        return clauses

    def _knowledge_search_text_expr(self):
        blank = literal_column("''")
        space = literal_column("' '")
        return func.lower(
            func.coalesce(KnowledgeChunk.path, blank)
            .op("||")(space)
            .op("||")(func.coalesce(KnowledgeChunk.directory, blank))
            .op("||")(space)
            .op("||")(func.coalesce(KnowledgeChunk.heading, blank))
            .op("||")(space)
            .op("||")(func.coalesce(KnowledgeChunk.tags_json, blank))
            .op("||")(space)
            .op("||")(func.coalesce(KnowledgeChunk.content, blank))
        )

    def _keyword_terms(self, query: str) -> list[str]:
        terms: list[str] = []
        for token in tokenize_text(query):
            normalized = token.strip().lower()
            if not normalized or normalized in terms:
                continue
            terms.append(normalized)
            if len(terms) >= 12:
                break
        return terms

    def _min_max_normalize(self, values: list[float]) -> list[float]:
        if not values:
            return []
        min_value = min(values)
        max_value = max(values)
        if min_value == max_value:
            if max_value <= 0:
                return [0.0 for _ in values]
            if 0.0 <= max_value <= 1.0:
                return [max_value for _ in values]
            return [1.0 for _ in values]
        scale = max_value - min_value
        return [(value - min_value) / scale for value in values]

    def _escape_like_value(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _like_pattern(self, value: str) -> str:
        return f"%{self._escape_like_value(value)}%"

    def _folder_prefix_pattern(self, value: str) -> str:
        return f"{self._escape_like_value(value)}/%"

    def _json_tag_pattern(self, value: str) -> str:
        return f'%"{self._escape_like_value(value)}"%'

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
