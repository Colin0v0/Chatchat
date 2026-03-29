from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from .chat_types import ChatImagePayload, ChatMessagePayload
from .image_text import ImageTextService
from .media import read_image_data_url
from .models import Message
from .providers import supports_native_image_input

DEFAULT_IMAGE_PROMPT = "Please describe the uploaded image in detail."
IMAGE_CONTEXT_LABEL = "Machine-generated image brief (may be inaccurate)"
IMAGE_ANALYSIS_SYSTEM_PROMPT = (
    "When the conversation includes uploaded images, you may receive a machine-generated image brief. "
    "Treat that brief as imperfect auxiliary evidence, not as authoritative fact, because it may contain recognition mistakes or missed details. "
    "If native image input is also present, prioritize the actual image and use the brief only as a cross-check. "
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
    def __init__(self, db: Session, image_text_service: ImageTextService):
        self._db = db
        self._image_text_service = image_text_service

    def needs_image_text(self, *, model: str, messages: list[Message]) -> bool:
        return any(message.attachments and not (message.image_context or "").strip() for message in messages)

    def needs_retrieval_grounding(self, *, messages: list[Message]) -> bool:
        return any(message.attachments and not (message.image_context or "").strip() for message in messages)

    async def prepare(self, *, model: str, messages: list[Message]) -> PreparedMessageHistory:
        prepared_messages: list[ChatMessagePayload] = []
        used_image_text = False
        contains_images = False

        for message in messages:
            prepared_message, used_text, has_images = await self._chat_message_payload(model=model, message=message)
            prepared_messages.append(prepared_message)
            used_image_text = used_image_text or used_text
            contains_images = contains_images or has_images

        if contains_images:
            prepared_messages = [
                ChatMessagePayload(role="system", content=IMAGE_ANALYSIS_SYSTEM_PROMPT),
                *prepared_messages,
            ]

        return PreparedMessageHistory(messages=prepared_messages, used_image_text=used_image_text)

    async def prepare_retrieval_history(self, *, messages: list[Message]) -> PreparedRetrievalHistory:
        prepared_messages: list[dict[str, str]] = []
        used_image_text = False
        for message in messages:
            content, used_text = await self._textual_message_content(message)
            prepared_messages.append({"role": message.role, "content": content})
            used_image_text = used_image_text or used_text
        return PreparedRetrievalHistory(messages=prepared_messages, used_image_text=used_image_text)

    async def _chat_message_payload(self, *, model: str, message: Message) -> tuple[ChatMessagePayload, bool, bool]:
        content, used_text = await self._textual_message_content(message)
        has_images = bool(message.attachments)
        if supports_native_image_input(model):
            return (
                ChatMessagePayload(
                    role=message.role,
                    content=content,
                    images=tuple(self._image_payloads(message)),
                ),
                used_text,
                has_images,
            )
        return ChatMessagePayload(role=message.role, content=content), used_text, has_images

    async def _textual_message_content(self, message: Message) -> tuple[str, bool]:
        if message.role != "user" or not message.attachments:
            return message.content, False

        image_context, used_text = await self._ensure_image_context(message)
        content_blocks = [self._resolved_user_prompt(message)]
        if image_context:
            content_blocks.append(f"{IMAGE_CONTEXT_LABEL}:\n{image_context}")
        return "\n\n".join(content_blocks), used_text

    async def _ensure_image_context(self, message: Message) -> tuple[str, bool]:
        cached_context = (message.image_context or "").strip()
        if cached_context:
            return cached_context, False

        result = await self._image_text_service.extract_markdown(message.attachments)
        message.image_context = result.markdown.strip()
        self._db.add(message)
        self._db.commit()
        self._db.refresh(message)
        return message.image_context, True

    def _resolved_user_prompt(self, message: Message) -> str:
        if message.role != "user" or not message.attachments:
            return message.content

        content = message.content.strip()
        if content:
            return content
        return DEFAULT_IMAGE_PROMPT

    def _image_payloads(self, message: Message) -> list[ChatImagePayload]:
        return [
            ChatImagePayload(
                mime_type=attachment.mime_type,
                data_url=read_image_data_url(attachment.relative_path, attachment.mime_type),
            )
            for attachment in message.attachments
            if attachment.kind == "image"
        ]
