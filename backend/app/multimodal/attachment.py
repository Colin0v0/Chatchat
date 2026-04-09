from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..storage.models import MessageAttachment
from .file_parser import FileParser
from .image import ImageTextService

IMAGE_SECTION_TITLE = "## Image attachments"
FILE_SECTION_TITLE = "## File attachments"


@dataclass(frozen=True)
class AttachmentContextResult:
    markdown: str
    has_images: bool
    has_files: bool


class AttachmentContextService:
    def __init__(
        self,
        *,
        image_service: ImageTextService,
        file_parser: FileParser,
        max_concurrency: int = 2,
    ):
        self._image_service = image_service
        self._file_parser = file_parser
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def _run_limited(self, coro):
        async with self._semaphore:
            return await coro

    async def extract_markdown(
        self,
        attachments: list[MessageAttachment],
        *,
        include_images: bool = True,
    ) -> AttachmentContextResult:
        image_attachments = [attachment for attachment in attachments if attachment.kind == "image"]
        file_attachments = [attachment for attachment in attachments if attachment.kind == "file"]

        blocks: list[str] = []
        if include_images and image_attachments:
            image_result = await self._run_limited(self._image_service.extract_markdown(image_attachments))
            blocks.append("\n\n".join([IMAGE_SECTION_TITLE, image_result.markdown]).strip())

        if file_attachments:
            file_markdown = await self._run_limited(
                asyncio.to_thread(self._file_parser.extract_markdown, file_attachments)
            )
            blocks.append("\n\n".join([FILE_SECTION_TITLE, file_markdown]).strip())

        return AttachmentContextResult(
            markdown="\n\n".join(blocks).strip(),
            has_images=bool(image_attachments),
            has_files=bool(file_attachments),
        )
