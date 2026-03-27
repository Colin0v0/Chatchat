from __future__ import annotations

import re
from dataclasses import dataclass

LEVEL2_HEADING_PATTERN = re.compile(r"^##(?!#)\s+(.*)\s*$")


@dataclass
class MarkdownSection:
    heading: str
    content: str


def split_markdown_by_level2(text: str) -> list[MarkdownSection]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")

    sections: list[MarkdownSection] = []
    current_heading = "Overview"
    buffer: list[str] = []

    for line in lines:
        matched = LEVEL2_HEADING_PATTERN.match(line)
        if matched:
            content = "\n".join(buffer).strip()
            if content:
                sections.append(MarkdownSection(heading=current_heading, content=content))
            current_heading = matched.group(1).strip() or "Untitled"
            buffer = []
            continue
        buffer.append(line)

    tail = "\n".join(buffer).strip()
    if tail:
        sections.append(MarkdownSection(heading=current_heading, content=tail))

    return sections
