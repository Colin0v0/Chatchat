from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .types import ChatFileReferencePayload, ChatMessagePayload
from .upstream_files import ensure_upstream_file_id
from ..multimodal.attachment import AttachmentContextService
from ..llm.catalog import uses_native_multimodal
from ..storage.models import Message

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
        if uses_native_multimodal(model):
            return False
        return any(message.attachments and not (message.attachment_context or "").strip() for message in messages)

    def needs_retrieval_grounding(self, *, messages: list[Message]) -> bool:
        return any(message.attachments and not (message.attachment_context or "").strip() for message in messages)

    async def prepare(self, *, model: str, messages: list[Message]) -> PreparedMessageHistory:
        prepared_messages: list[ChatMessagePayload] = []
        used_image_text = False
        contains_image_brief = False

        for message in messages:
            prepared_message, used_text, has_image_brief = await self._chat_message_payload(model=model, message=message)
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
        for message in messages:
            content, used_text = await self._textual_message_content(model=model, message=message)
            prepared_messages.append({"role": message.role, "content": content})
            used_image_text = used_image_text or used_text
        return PreparedRetrievalHistory(messages=prepared_messages, used_image_text=used_image_text)

    async def _chat_message_payload(self, *, model: str, message: Message) -> tuple[ChatMessagePayload, bool, bool]:
        if message.role == "user" and message.attachments and uses_native_multimodal(model):
            return (
                ChatMessagePayload(
                    role=message.role,
                    content=self._resolved_user_prompt(message),
                    files=tuple(await self._file_references(model=model, message=message)),
                ),
                False,
                False,
            )

        content, used_text = await self._textual_message_content(model=model, message=message)
        has_images = any(attachment.kind == "image" for attachment in message.attachments)
        return ChatMessagePayload(role=message.role, content=content), used_text, has_images

    async def _textual_message_content(self, *, model: str, message: Message) -> tuple[str, bool]:
        if message.role != "user" or not message.attachments:
            return message.content, False

        if uses_native_multimodal(model):
            return self._resolved_user_prompt(message), False

        attachment_context, used_text = await self._ensure_attachment_context(model=model, message=message)
        content_blocks = [self._resolved_user_prompt(message)]
        if attachment_context:
            content_blocks.append(f"{ATTACHMENT_CONTEXT_LABEL}:\n{attachment_context}")
        return "\n\n".join(content_blocks), used_text

    async def _ensure_attachment_context(self, *, model: str, message: Message) -> tuple[str, bool]:
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

    def _resolved_user_prompt(self, message: Message) -> str:
        if message.role != "user" or not message.attachments:
            return message.content

        content = message.content.strip()
        if content:
            return content
        return DEFAULT_ATTACHMENT_PROMPT

    async def _file_references(self, *, model: str, message: Message) -> list[ChatFileReferencePayload]:
        references: list[ChatFileReferencePayload] = []
        for attachment in message.attachments:
            file_id = await ensure_upstream_file_id(
                db=self._db,
                model=model,
                attachment=attachment,
            )
            references.append(ChatFileReferencePayload(file_id=file_id))
        return references
