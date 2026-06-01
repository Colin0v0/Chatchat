from __future__ import annotations

import base64
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .types import ChatDocumentPayload, ChatFileReferencePayload, ChatImagePayload, ChatMessagePayload
from .upstream_files import ensure_upstream_file_id
from ..llm.capabilities import NativeMultimodalMode
from ..multimodal.attachment import AttachmentContextService
from ..providers import resolve_native_multimodal_mode
from ..storage.media import read_image_data_url, resolve_media_file_path
from ..storage.models import Message, MessageAttachment

DEFAULT_ATTACHMENT_PROMPT = "Please analyze the uploaded attachments in detail."
ATTACHMENT_CONTEXT_LABEL = "Machine-generated attachment brief (may be inaccurate)"
IMAGE_ANALYSIS_SYSTEM_PROMPT = (
    "When the conversation includes uploaded images, you may receive a machine-generated image brief. "
    "Treat that brief as imperfect auxiliary evidence, not as authoritative fact, because it may contain recognition mistakes or missed details. "
    "Answer with concrete visual details first: subject, appearance, clothing, pose, objects, background, composition, colors, style, mood, and any visible text. "
    "For identity, character, or franchise questions, default to cautious wording such as looks like, may be, or possibly, unless the image itself makes the answer clear. "
    "If the evidence is weak, say that the identification may be inaccurate or uncertain. "
    "Do not invent hidden facts that are not supported by the image or by clearly visible evidence."
)
ATTACHMENT_REFERENCE_MARKERS = (
    "这张图",
    "那张图",
    "上面的图",
    "刚才的图",
    "这个图片",
    "那个图片",
    "这个文件",
    "那个文件",
    "上面的文件",
    "刚才的文件",
    "这个pdf",
    "那个pdf",
    "这个文档",
    "那个文档",
)
ATTACHMENT_REFERENCE_MARKERS_FOLDED = tuple(value.lower() for value in ATTACHMENT_REFERENCE_MARKERS)


def read_attachment_base64(relative_path: str) -> str:
    file_path = resolve_media_file_path(relative_path)
    return base64.b64encode(file_path.read_bytes()).decode("ascii")


@dataclass(frozen=True)
class PreparedMessageHistory:
    messages: list[ChatMessagePayload]
    used_image_text: bool = False


@dataclass(frozen=True)
class PreparedRetrievalHistory:
    messages: list[dict[str, str]]
    used_image_text: bool = False


class MessageHistoryService:
    def __init__(self, db: Session, attachment_context_service: AttachmentContextService):
        self._db = db
        self._attachment_context_service = attachment_context_service

    def needs_image_text(self, *, model: str, messages: list[Message]) -> bool:
        native_mode = resolve_native_multimodal_mode(model)
        if native_mode != "false":
            return False
        active_ids = self._active_attachment_message_ids(messages)
        return any(
            id(message) in active_ids and message.attachments and not (message.attachment_context or "").strip()
            for message in messages
        )

    def needs_retrieval_grounding(self, *, model: str, messages: list[Message]) -> bool:
        native_mode = resolve_native_multimodal_mode(model)
        active_ids = self._active_attachment_message_ids(messages)
        return any(
            id(message) in active_ids and self._requires_local_file_context(native_mode=native_mode, message=message)
            for message in messages
        )

    async def prepare(self, *, model: str, messages: list[Message]) -> PreparedMessageHistory:
        prepared_messages: list[ChatMessagePayload] = []
        used_image_text = False
        contains_image_brief = False
        active_attachment_ids = self._active_attachment_message_ids(messages)

        for message in messages:
            prepared_message, used_text, has_image_brief = await self._chat_message_payload(
                model=model,
                message=message,
                include_attachment_context=id(message) in active_attachment_ids,
            )
            prepared_messages.append(prepared_message)
            used_image_text = used_image_text or used_text
            contains_image_brief = contains_image_brief or has_image_brief

        if contains_image_brief:
            prepared_messages = [
                ChatMessagePayload(role="system", content=IMAGE_ANALYSIS_SYSTEM_PROMPT),
                *prepared_messages,
            ]

        return PreparedMessageHistory(messages=prepared_messages, used_image_text=used_image_text)

    async def prepare_retrieval_history(self, *, model: str, messages: list[Message]) -> PreparedRetrievalHistory:
        prepared_messages: list[dict[str, str]] = []
        used_image_text = False
        active_attachment_ids = self._active_attachment_message_ids(messages)
        for message in messages:
            content, used_text = await self._textual_message_content(
                model=model,
                message=message,
                include_attachment_context=id(message) in active_attachment_ids,
            )
            prepared_messages.append({"role": message.role, "content": content})
            used_image_text = used_image_text or used_text
        return PreparedRetrievalHistory(messages=prepared_messages, used_image_text=used_image_text)

    async def _chat_message_payload(
        self,
        *,
        model: str,
        message: Message,
        include_attachment_context: bool,
    ) -> tuple[ChatMessagePayload, bool, bool]:
        native_mode = resolve_native_multimodal_mode(model)
        if message.role == "user" and message.attachments and include_attachment_context and native_mode in ("codex", "gemini", "claude"):
            content, used_text = await self._native_multimodal_message_content(
                native_mode=native_mode,
                message=message,
                include_attachment_context=include_attachment_context,
            )
            return (
                ChatMessagePayload(
                    role=message.role,
                    content=content,
                    images=tuple(self._image_payloads(message)),
                    documents=tuple(self._document_payloads(message=message, native_mode=native_mode)),
                    files=tuple(await self._native_file_references(model=model, message=message, native_mode=native_mode)),
                ),
                used_text,
                False,
            )

        content, used_text = await self._textual_message_content(
            model=model,
            message=message,
            include_attachment_context=include_attachment_context,
        )
        has_images = include_attachment_context and any(attachment.kind == "image" for attachment in message.attachments)
        return ChatMessagePayload(role=message.role, content=content), used_text, has_images

    async def _textual_message_content(
        self,
        *,
        model: str,
        message: Message,
        include_attachment_context: bool,
    ) -> tuple[str, bool]:
        if message.role != "user" or not message.attachments:
            return message.content, False

        native_mode = resolve_native_multimodal_mode(model)
        if not include_attachment_context:
            return self._resolved_user_prompt(message), False

        if native_mode in ("codex", "gemini", "claude"):
            attachment_context, used_text = await self._ensure_selected_file_attachment_context(
                message=message,
                attachments=self._local_file_attachments(message, native_mode=native_mode),
            )
        else:
            attachment_context, used_text = await self._ensure_attachment_context(message=message)
        content_blocks = [self._resolved_user_prompt(message)]
        if attachment_context:
            content_blocks.append(f"{ATTACHMENT_CONTEXT_LABEL}:\n{attachment_context}")
        return "\n\n".join(content_blocks), used_text

    async def _ensure_attachment_context(self, *, message: Message) -> tuple[str, bool]:
        cached_context = (message.attachment_context or "").strip()
        if cached_context:
            return cached_context, False

        result = await self._attachment_context_service.extract_markdown(
            message.attachments,
            include_images=True,
        )
        message.attachment_context = result.markdown.strip()
        if result.has_images and not (message.image_context or "").strip():
            message.image_context = message.attachment_context
        self._db.add(message)
        self._db.commit()
        self._db.refresh(message)
        return message.attachment_context, True

    async def _native_multimodal_message_content(
        self,
        *,
        native_mode: NativeMultimodalMode,
        message: Message,
        include_attachment_context: bool,
    ) -> tuple[str, bool]:
        content = self._resolved_user_prompt(message)
        if not include_attachment_context:
            return content, False

        local_file_attachments = self._local_file_attachments(message, native_mode=native_mode)
        if not local_file_attachments:
            return content, False

        attachment_context, used_text = await self._ensure_selected_file_attachment_context(
            message=message,
            attachments=local_file_attachments,
        )
        if not attachment_context:
            return content, used_text
        return "\n\n".join([content, f"{ATTACHMENT_CONTEXT_LABEL}:\n{attachment_context}"]), used_text

    async def _ensure_selected_file_attachment_context(
        self,
        *,
        message: Message,
        attachments: list[MessageAttachment],
    ) -> tuple[str, bool]:
        if not attachments:
            return "", False
        result = await self._attachment_context_service.extract_markdown(attachments, include_images=False)
        return result.markdown.strip(), True

    def _resolved_user_prompt(self, message: Message) -> str:
        if message.role != "user" or not message.attachments:
            return message.content

        content = message.content.strip()
        if content:
            return content
        return DEFAULT_ATTACHMENT_PROMPT

    async def _native_file_references(
        self,
        *,
        model: str,
        message: Message,
        native_mode: NativeMultimodalMode,
    ) -> list[ChatFileReferencePayload]:
        references: list[ChatFileReferencePayload] = []
        if native_mode != "codex":
            return references
        for attachment in self._native_file_attachments(message, native_mode=native_mode):
            file_id = await ensure_upstream_file_id(
                db=self._db,
                model=model,
                attachment=attachment,
            )
            references.append(ChatFileReferencePayload(file_id=file_id))
        return references

    def _document_payloads(
        self,
        *,
        message: Message,
        native_mode: NativeMultimodalMode,
    ) -> list[ChatDocumentPayload]:
        if native_mode not in ("gemini", "claude"):
            return []
        return [
            ChatDocumentPayload(
                mime_type=attachment.mime_type,
                filename=attachment.original_name,
                base64_data=read_attachment_base64(attachment.relative_path),
            )
            for attachment in self._native_file_attachments(message, native_mode=native_mode)
        ]

    def _image_payloads(self, message: Message) -> list[ChatImagePayload]:
        payloads: list[ChatImagePayload] = []
        for attachment in message.attachments:
            if attachment.kind != "image":
                continue
            payloads.append(
                ChatImagePayload(
                    mime_type=attachment.mime_type,
                    data_url=read_image_data_url(attachment.relative_path, attachment.mime_type),
                )
            )
        return payloads

    def _native_file_attachments(
        self,
        message: Message,
        *,
        native_mode: NativeMultimodalMode,
    ) -> list[MessageAttachment]:
        if native_mode not in ("codex", "gemini", "claude"):
            return []
        return [
            attachment
            for attachment in message.attachments
            if attachment.kind == "file" and attachment.mime_type.split(";", 1)[0].strip().lower() == "application/pdf"
        ]

    def _local_file_attachments(
        self,
        message: Message,
        *,
        native_mode: NativeMultimodalMode,
    ) -> list[MessageAttachment]:
        native_ids = {id(attachment) for attachment in self._native_file_attachments(message, native_mode=native_mode)}
        return [
            attachment
            for attachment in message.attachments
            if attachment.kind == "file" and id(attachment) not in native_ids
        ]

    def _requires_local_file_context(self, *, native_mode: str, message: Message) -> bool:
        if message.role != "user" or not message.attachments:
            return False
        if native_mode == "false":
            return not (message.attachment_context or "").strip()
        if native_mode in ("codex", "gemini", "claude"):
            return bool(self._local_file_attachments(message, native_mode=native_mode))
        return False

    def _active_attachment_message_ids(self, messages: list[Message]) -> set[int]:
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

        latest_text = (latest_user.content or "").strip()
        if latest_text and any(marker in latest_text.lower() for marker in ATTACHMENT_REFERENCE_MARKERS_FOLDED):
            for message in reversed(attachment_messages):
                if id(message) == id(latest_user):
                    continue
                active_ids.add(id(message))
                break
        return active_ids
