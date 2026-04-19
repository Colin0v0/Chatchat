from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ..core.config import settings
from ..multimodal.file_types import resolve_attachment_type


@dataclass(frozen=True)
class StoredAttachment:
    kind: str
    original_name: str
    mime_type: str
    relative_path: str
    size_bytes: int
    extension: str


def _resolve_media_root(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / raw_path
    path.mkdir(parents=True, exist_ok=True)
    return path


MEDIA_ROOT = _resolve_media_root(settings.media_root)


def media_url(relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    return f"/media/{normalized}"


async def persist_uploaded_attachments(files: list[UploadFile]) -> list[StoredAttachment]:
    uploads = [file for file in files if file.filename or file.content_type]
    if not uploads:
        return []

    if len(uploads) > settings.attachment_max_upload_count:
        raise ValueError(
            f"You can upload up to {settings.attachment_max_upload_count} attachments per message."
        )

    saved_attachments: list[StoredAttachment] = []
    for upload in uploads:
        attachment_type = resolve_attachment_type(upload.filename or "", upload.content_type or "")
        mime_type = attachment_type.mime_type

        content = await upload.read()
        await upload.close()
        if not content:
            raise ValueError("One of the uploaded files is empty.")
        if len(content) > settings.attachment_max_upload_size_bytes:
            max_megabytes = settings.attachment_max_upload_size_bytes // (1024 * 1024)
            raise ValueError(f"Each file must be {max_megabytes} MB or smaller.")

        today = datetime.utcnow()
        relative_path = (
            Path("images" if attachment_type.kind == "image" else "files")
            / today.strftime("%Y")
            / today.strftime("%m")
            / today.strftime("%d")
            / f"{uuid4().hex}{attachment_type.extension}"
        )
        file_path = MEDIA_ROOT / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)

        saved_attachments.append(
            StoredAttachment(
                kind=attachment_type.kind,
                original_name=(upload.filename or file_path.name).strip() or file_path.name,
                mime_type=mime_type,
                relative_path=relative_path.as_posix(),
                size_bytes=len(content),
                extension=attachment_type.extension,
            )
        )

    return saved_attachments


def read_image_data_url(relative_path: str, mime_type: str) -> str:
    file_path = MEDIA_ROOT / Path(relative_path)
    raw = file_path.read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def remove_media_files(relative_paths: list[str]) -> None:
    for relative_path in dict.fromkeys(path for path in relative_paths if path):
        file_path = MEDIA_ROOT / Path(relative_path)
        if file_path.exists():
            file_path.unlink()
