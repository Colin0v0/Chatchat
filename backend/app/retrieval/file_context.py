from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy.orm import Session

from ..chat.token_budget import estimate_text_tokens, truncate_text_to_token_budget
from ..core.config import Settings
from ..multimodal.attachment import AttachmentContextService
from ..storage.models import Message
from .types import ContextEntry, ContextPayload, SourceItem

TERM_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}")
ATTACHMENT_REFERENCE_MARKERS = (
    "这张图",
    "那张图",
    "上面的图",
    "刚才的图",
    "这个文件",
    "那个文件",
    "上面的文件",
    "刚才的文件",
    "这个pdf",
    "那个pdf",
    "这个文档",
    "那个文档",
)


@dataclass(frozen=True)
class FileChunk:
    message: Message
    label: str
    content: str


class ConversationFileContextService:
    def __init__(self, settings: Settings, attachment_context_service: AttachmentContextService):
        self._attachment_context_service = attachment_context_service
        self._top_k = max(1, settings.file_retrieval_top_k)
        self._chunk_token_limit = max(64, settings.file_retrieval_chunk_token_limit)
        self._min_score = max(0.0, settings.file_retrieval_min_score)

    async def retrieve_context(
        self,
        *,
        db: Session,
        query: str,
        messages: list[Message],
        include_images: bool,
    ) -> ContextPayload:
        normalized_query = query.strip()
        if not normalized_query:
            return ContextPayload()

        active_message_ids = self._active_attachment_message_ids(messages=messages, query=normalized_query)
        chunks = await self._build_chunks(
            db=db,
            messages=messages,
            include_images=include_images,
            active_message_ids=active_message_ids,
        )
        if not chunks:
            return ContextPayload()

        scored: list[tuple[float, FileChunk]] = []
        query_terms = self._terms(normalized_query)
        if not query_terms:
            return ContextPayload()

        for chunk in chunks:
            score = self._score_chunk(query_terms=query_terms, chunk=chunk)
            if score >= self._min_score:
                scored.append((score, chunk))

        ranked = sorted(scored, key=lambda item: item[0], reverse=True)[: self._top_k]
        if not ranked:
            return ContextPayload()

        sources = [
            SourceItem(
                type="file",
                path=self._source_path(chunk),
                heading=chunk.label,
                excerpt=truncate_text_to_token_budget(chunk.content, token_budget=72),
                score=score,
                title=chunk.label,
            )
            for score, chunk in ranked
        ]
        entries = [
            ContextEntry(
                source=SourceItem(
                    type="file",
                    path=self._source_path(chunk),
                    heading=chunk.label,
                    excerpt=truncate_text_to_token_budget(chunk.content, token_budget=72),
                    score=score,
                    title=chunk.label,
                ),
                content=chunk.content,
            )
            for score, chunk in ranked
        ]
        return ContextPayload(entries=entries, sources=sources, debug={"file_hits": len(ranked)})

    async def _build_chunks(
        self,
        *,
        db: Session,
        messages: list[Message],
        include_images: bool,
        active_message_ids: set[int],
    ) -> list[FileChunk]:
        chunks: list[FileChunk] = []
        for message in messages:
            if id(message) not in active_message_ids:
                continue
            if message.role != "user" or not message.attachments:
                continue

            has_image_attachments = any(attachment.kind == "image" for attachment in message.attachments)
            context_attachments = message.attachments if include_images else [
                attachment for attachment in message.attachments if attachment.kind == "file"
            ]
            if not context_attachments:
                continue

            attachment_context = (message.attachment_context or "").strip()
            should_reuse_cache = include_images or not has_image_attachments
            if not attachment_context or not should_reuse_cache:
                result = await self._attachment_context_service.extract_markdown(
                    context_attachments,
                    include_images=include_images,
                )
                attachment_context = result.markdown.strip()
                if not attachment_context:
                    continue
                if should_reuse_cache:
                    message.attachment_context = attachment_context
                    if result.has_images and not (message.image_context or "").strip():
                        message.image_context = attachment_context
                    db.add(message)
                    db.commit()
                    db.refresh(message)

            base_label = ", ".join(attachment.original_name for attachment in message.attachments[:3])
            if len(message.attachments) > 3:
                base_label += ", …"
            chunks.extend(self._split_context(message=message, label=base_label, content=attachment_context))
        return chunks

    def _active_attachment_message_ids(self, *, messages: list[Message], query: str) -> set[int]:
        attachment_messages = [
            message
            for message in messages
            if message.role == "user" and message.attachments
        ]
        if not attachment_messages:
            return set()

        latest_user = next((message for message in reversed(messages) if message.role == "user"), None)
        if latest_user is None:
            return set()

        active_ids: set[int] = set()
        if latest_user.attachments:
            active_ids.add(id(latest_user))
        folded_query = query.lower()
        if any(marker.lower() in folded_query for marker in ATTACHMENT_REFERENCE_MARKERS):
            for message in reversed(attachment_messages):
                if id(message) == id(latest_user):
                    continue
                active_ids.add(id(message))
                break
        return active_ids

    def _split_context(self, *, message: Message, label: str, content: str) -> list[FileChunk]:
        paragraphs = [paragraph.strip() for paragraph in content.split("\n\n") if paragraph.strip()]
        if not paragraphs:
            return []

        chunks: list[FileChunk] = []
        current_parts: list[str] = []
        current_tokens = 0
        section_index = 1

        for paragraph in paragraphs:
            paragraph_tokens = estimate_text_tokens(paragraph)
            if current_parts and current_tokens + paragraph_tokens > self._chunk_token_limit:
                chunks.append(
                    FileChunk(
                        message=message,
                        label=f"{label} · Part {section_index}",
                        content="\n\n".join(current_parts),
                    )
                )
                current_parts = []
                current_tokens = 0
                section_index += 1

            if paragraph_tokens > self._chunk_token_limit:
                paragraph = truncate_text_to_token_budget(paragraph, token_budget=self._chunk_token_limit)
                paragraph_tokens = estimate_text_tokens(paragraph)

            current_parts.append(paragraph)
            current_tokens += paragraph_tokens

        if current_parts:
            chunks.append(
                FileChunk(
                    message=message,
                    label=f"{label} · Part {section_index}",
                    content="\n\n".join(current_parts),
                )
            )
        return chunks

    def _score_chunk(self, *, query_terms: set[str], chunk: FileChunk) -> float:
        haystack_terms = self._terms(" ".join([chunk.label, chunk.content, chunk.message.content]))
        if not haystack_terms:
            return 0.0

        overlap = query_terms & haystack_terms
        if not overlap:
            return 0.0
        return len(overlap) / len(query_terms)

    def _terms(self, value: str) -> set[str]:
        terms: set[str] = set()
        for term in TERM_PATTERN.findall(value.lower()):
            normalized = term.strip()
            if len(normalized) >= 2:
                terms.add(normalized)
                if normalized.isascii():
                    continue
                for size in (2, 3):
                    if len(normalized) < size:
                        continue
                    for index in range(len(normalized) - size + 1):
                        terms.add(normalized[index : index + size])
        return terms

    def _source_path(self, chunk: FileChunk) -> str:
        attachments = chunk.message.attachments
        if not attachments:
            return ""
        return attachments[0].relative_path
