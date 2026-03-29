from __future__ import annotations

import hashlib
from pathlib import Path
import re

from .splitter import split_markdown_by_level2
from .types import MarkdownDocument, RagChunkSpec
from .text import normalize_tag

FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
INLINE_TAG_PATTERN = re.compile(r"(?<!\w)#([A-Za-z0-9_/\-]+)")


def collect_markdown_documents(vault_path: Path) -> list[MarkdownDocument]:
    if not vault_path.exists():
        return []

    documents: list[MarkdownDocument] = []
    for file_path in sorted(vault_path.rglob("*.md")):
        if ".obsidian" in file_path.parts:
            continue

        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        relative_path = file_path.relative_to(vault_path).as_posix()
        signature = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        documents.append(
            MarkdownDocument(
                path=relative_path,
                content=raw,
                signature=signature,
            )
        )
    return documents


def build_chunk_specs_for_document(
    document: MarkdownDocument, section_max_chars: int
) -> list[RagChunkSpec]:
    sections = split_markdown_by_level2(document.content)
    chunk_specs: list[RagChunkSpec] = []
    tags = extract_document_tags(document.content)
    directory = document.path.rsplit("/", 1)[0] if "/" in document.path else ""
    chunk_order = 0

    for section_index, section in enumerate(sections):
        segmented_contents = split_large_section(section.content, section_max_chars)
        for segment_index, content in enumerate(segmented_contents):
            if not content:
                continue

            heading = section.heading
            if len(segmented_contents) > 1:
                heading = f"{section.heading} (part {segment_index + 1})"

            chunk_hash = hashlib.sha1(
                f"{document.path}:{heading}:{section_index}:{segment_index}:{content}".encode(
                    "utf-8"
                )
            ).hexdigest()
            chunk_specs.append(
                RagChunkSpec(
                    id=chunk_hash,
                    path=document.path,
                    directory=directory,
                    heading=heading,
                    content=content,
                    order=chunk_order,
                    tags=tags,
                )
            )
            chunk_order += 1

    return chunk_specs


def split_large_section(text: str, section_max_chars: int) -> list[str]:
    content = text.strip()
    if not content:
        return []
    if len(content) <= section_max_chars:
        return [content]

    paragraphs = [item.strip() for item in content.split("\n\n") if item.strip()]
    segments: list[str] = []
    buffer = ""

    for paragraph in paragraphs:
        if len(paragraph) > section_max_chars:
            if buffer:
                segments.append(buffer)
                buffer = ""
            segments.extend(split_long_paragraph(paragraph, section_max_chars))
            continue

        if not buffer:
            buffer = paragraph
            continue

        candidate = f"{buffer}\n\n{paragraph}"
        if len(candidate) <= section_max_chars:
            buffer = candidate
        else:
            segments.append(buffer)
            buffer = paragraph

    if buffer:
        segments.append(buffer)

    return segments if segments else [content]


def split_long_paragraph(paragraph: str, section_max_chars: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(paragraph):
        end = min(start + section_max_chars, len(paragraph))
        chunks.append(paragraph[start:end].strip())
        start = end
    return [chunk for chunk in chunks if chunk]


def extract_document_tags(text: str) -> list[str]:
    tags: list[str] = []
    tags.extend(_extract_frontmatter_tags(text))
    tags.extend(normalize_tag(item) for item in INLINE_TAG_PATTERN.findall(text))

    unique_tags: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        if not tag or tag in seen:
            continue
        seen.add(tag)
        unique_tags.append(tag)
    return unique_tags


def _extract_frontmatter_tags(text: str) -> list[str]:
    matched = FRONTMATTER_PATTERN.match(text)
    if not matched:
        return []

    lines = matched.group(1).splitlines()
    tags: list[str] = []
    inside_tags = False
    tags_indent = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        current_indent = len(line) - len(line.lstrip())
        if inside_tags:
            if current_indent <= tags_indent and not stripped.startswith("-"):
                inside_tags = False
            elif stripped.startswith("-"):
                value = normalize_tag(stripped[1:].strip())
                if value:
                    tags.append(value)
                continue
            else:
                value = normalize_tag(stripped)
                if value:
                    tags.append(value)
                continue

        if not stripped.startswith("tags:"):
            continue

        rest = stripped[5:].strip()
        if rest.startswith("[") and rest.endswith("]"):
            values = [normalize_tag(item) for item in rest[1:-1].split(",")]
            tags.extend(value for value in values if value)
            continue
        if rest:
            values = [normalize_tag(item) for item in rest.split(",")]
            tags.extend(value for value in values if value)
            continue

        inside_tags = True
        tags_indent = current_indent

    return tags
