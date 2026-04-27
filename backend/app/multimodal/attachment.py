from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ..storage.models import MessageAttachment
from .file_parser import FileParser

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
        file_parser: FileParser,
        max_concurrency: int = 2,
    ):
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
        file_attachments = [attachment for attachment in attachments if attachment.kind == "file"]

        blocks: list[str] = []
        if file_attachments:
            file_markdown = await self._run_limited(
                asyncio.to_thread(self._file_parser.extract_markdown, file_attachments)
            )
            blocks.append("\n\n".join([FILE_SECTION_TITLE, file_markdown]).strip())

        return AttachmentContextResult(
            markdown="\n\n".join(blocks).strip(),
            has_images=False,
            has_files=bool(file_attachments),
        )
