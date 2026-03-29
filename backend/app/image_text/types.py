from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImageTextResult:
    markdown: str
    has_visible_text: bool
    has_visual_summary: bool
