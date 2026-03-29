from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from .config import settings

ALLOWED_IMAGE_MIME_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


@dataclass(frozen=True)
class StoredImage:
    original_name: str
    mime_type: str
    relative_path: str
    size_bytes: int


def _resolve_media_root(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / raw_path
    path.mkdir(parents=True, exist_ok=True)
    return path


MEDIA_ROOT = _resolve_media_root(settings.media_root)


def media_url(relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/").lstrip("/")
    return f"/media/{normalized}"


async def persist_uploaded_images(files: list[UploadFile]) -> list[StoredImage]:
    uploads = [file for file in files if file.filename or file.content_type]
    if not uploads:
        return []

    if len(uploads) > settings.image_max_upload_count:
        raise ValueError(f"You can upload up to {settings.image_max_upload_count} images per message.")

    saved_images: list[StoredImage] = []
    for upload in uploads:
        mime_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
        suffix = ALLOWED_IMAGE_MIME_TYPES.get(mime_type)
        if suffix is None:
            raise ValueError("Only PNG, JPG, WEBP, and GIF images are supported.")

        content = await upload.read()
        await upload.close()
        if not content:
            raise ValueError("One of the uploaded images is empty.")
        if len(content) > settings.image_max_upload_size_bytes:
            max_megabytes = settings.image_max_upload_size_bytes // (1024 * 1024)
            raise ValueError(f"Each image must be {max_megabytes} MB or smaller.")

        today = datetime.utcnow()
        relative_path = (
            Path("images")
            / today.strftime("%Y")
            / today.strftime("%m")
            / today.strftime("%d")
            / f"{uuid4().hex}{suffix}"
        )
        file_path = MEDIA_ROOT / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)

        saved_images.append(
            StoredImage(
                original_name=(upload.filename or file_path.name).strip() or file_path.name,
                mime_type=mime_type,
                relative_path=relative_path.as_posix(),
                size_bytes=len(content),
            )
        )

    return saved_images


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
