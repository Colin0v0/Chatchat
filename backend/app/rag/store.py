from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .types import RagChunk


@dataclass(frozen=True)
class RagIndexSnapshot:
    chunks: list[RagChunk]
    updated_at: str | None
    embedding_model: str | None
    section_max_chars: int | None
    file_signatures: dict[str, str]


class RagIndexStore:
    def __init__(self, index_path: Path):
        self._index_path = index_path

    def load(self) -> RagIndexSnapshot:
        if not self._index_path.exists():
            return RagIndexSnapshot(
                chunks=[],
                updated_at=None,
                embedding_model=None,
                section_max_chars=None,
                file_signatures={},
            )

        try:
            payload = json.loads(self._index_path.read_text(encoding="utf-8"))
            chunk_items = payload.get("chunks", [])
            chunks = [
                RagChunk(
                    id=item["id"],
                    path=item["path"],
                    directory=str(item.get("directory", "")).strip()
                    or _directory_from_path(str(item["path"])),
                    heading=item["heading"],
                    content=item["content"],
                    order=_coerce_order(item.get("order"), index),
                    embedding=[float(value) for value in item["embedding"]],
                    tags=_coerce_tags(item.get("tags")),
                )
                for index, item in enumerate(chunk_items)
            ]

            section_max_chars = payload.get("section_max_chars")
            if not isinstance(section_max_chars, int) or section_max_chars <= 0:
                section_max_chars = None

            signatures = payload.get("file_signatures", {})
            if isinstance(signatures, dict):
                file_signatures = {
                    str(path): str(signature)
                    for path, signature in signatures.items()
                    if str(path).strip() and str(signature).strip()
                }
            else:
                file_signatures = {}

            embedding_model = str(payload.get("embedding_model", "")).strip() or None
            updated_at = payload.get("updated_at")
            if not isinstance(updated_at, str):
                updated_at = None

            return RagIndexSnapshot(
                chunks=chunks,
                updated_at=updated_at,
                embedding_model=embedding_model,
                section_max_chars=section_max_chars,
                file_signatures=file_signatures,
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return RagIndexSnapshot(
                chunks=[],
                updated_at=None,
                embedding_model=None,
                section_max_chars=None,
                file_signatures={},
            )

    def write(
        self,
        *,
        updated_at: str | None,
        embedding_model: str,
        section_max_chars: int,
        file_signatures: dict[str, str],
        chunks: list[RagChunk],
    ) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": updated_at,
            "embedding_model": embedding_model,
            "section_max_chars": section_max_chars,
            "file_signatures": file_signatures,
            "chunks": [
                {
                    "id": chunk.id,
                    "path": chunk.path,
                    "directory": chunk.directory,
                    "heading": chunk.heading,
                    "content": chunk.content,
                    "order": chunk.order,
                    "embedding": chunk.embedding,
                    "tags": chunk.tags,
                }
                for chunk in chunks
            ],
        }
        self._index_path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )


def _directory_from_path(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _coerce_order(value: object, default: int) -> int:
    if isinstance(value, int) and value >= 0:
        return value
    return default


def _coerce_tags(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    tags: list[str] = []
    for item in value:
        normalized = str(item).strip().lower()
        if not normalized or normalized in tags:
            continue
        tags.append(normalized)
    return tags
