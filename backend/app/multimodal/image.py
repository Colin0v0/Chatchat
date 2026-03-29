from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Sequence

from ..storage.media import MEDIA_ROOT
from ..storage.models import MessageAttachment
from .ocr import ImageOcr
from .types import ImageTextResult
from .vision import ImageVision

NO_TEXT_MARKDOWN = "No readable text was detected in the uploaded image."


class ImageTextService:
    def __init__(
        self,
        *,
        min_confidence: float,
        text_max_chars: int,
        vision_model_name: str,
        vision_prompt: str,
        vision_max_new_tokens: int,
        vision_num_beams: int,
        vision_summary_max_chars: int,
        vision_device: str,
    ):
        self._text_max_chars = max(1, text_max_chars)
        self._vision_summary_max_chars = max(1, vision_summary_max_chars)
        self._ocr = ImageOcr(min_confidence=min_confidence)
        self._vision = ImageVision(
            model_name=vision_model_name,
            prompt=vision_prompt,
            max_new_tokens=vision_max_new_tokens,
            num_beams=vision_num_beams,
            device=vision_device,
        )

    async def extract_markdown(self, attachments: Sequence[MessageAttachment]) -> ImageTextResult:
        return await asyncio.to_thread(self._extract_markdown_sync, tuple(attachments))

    def _extract_markdown_sync(self, attachments: Sequence[MessageAttachment]) -> ImageTextResult:
        image_attachments = [attachment for attachment in attachments if attachment.kind == "image"]
        image_blocks: list[str] = []
        has_visible_text = False

        for index, attachment in enumerate(image_attachments, start=1):
            image_path = MEDIA_ROOT / Path(attachment.relative_path)
            visual_summary = self._normalize_visual_summary(self._vision.describe(image_path).summary)
            ocr_lines = self._ocr.extract_lines(image_path)
            visible_text = self._normalize_visible_text([line.text for line in ocr_lines])
            has_visible_text = has_visible_text or bool(ocr_lines)
            image_blocks.append(
                self._build_image_block(
                    index=index,
                    visual_summary=visual_summary,
                    visible_text=visible_text,
                )
            )

        markdown = self._build_markdown(image_blocks=image_blocks)
        return ImageTextResult(
            markdown=self._truncate_markdown(markdown),
            has_visible_text=has_visible_text,
            has_visual_summary=bool(image_blocks),
        )

    def _build_image_block(self, *, index: int, visual_summary: str, visible_text: str) -> str:
        return "\n".join(
            [
                f"### Image {index}",
                "Detailed visual observations:",
                visual_summary,
                "",
                "Visible text:",
                visible_text,
            ]
        ).strip()

    def _build_markdown(self, *, image_blocks: list[str]) -> str:
        if not image_blocks:
            raise RuntimeError("The local vision model did not return any image description.")
        return "\n\n".join(["## Structured image brief", *image_blocks]).strip()

    def _normalize_visual_summary(self, summary: str) -> str:
        normalized = " ".join(summary.split()).strip()
        if len(normalized) <= self._vision_summary_max_chars:
            return normalized
        cutoff = max(0, self._vision_summary_max_chars - 3)
        return normalized[:cutoff].rstrip() + "..."

    def _normalize_visible_text(self, lines: list[str]) -> str:
        normalized_lines = [" ".join(line.split()).strip() for line in lines if " ".join(line.split()).strip()]
        if not normalized_lines:
            return NO_TEXT_MARKDOWN
        return "\n".join(f"- {line}" for line in normalized_lines)

    def _truncate_markdown(self, markdown: str) -> str:
        normalized = markdown.strip()
        if len(normalized) <= self._text_max_chars:
            return normalized
        cutoff = max(0, self._text_max_chars - 3)
        return normalized[:cutoff].rstrip() + "..."
