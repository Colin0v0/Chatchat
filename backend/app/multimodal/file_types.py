from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

IMAGE_MIME_TO_EXTENSION: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

DOCUMENT_MIME_TO_EXTENSION: dict[str, str] = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/x-python": ".py",
    "text/javascript": ".js",
    "text/typescript": ".ts",
    "text/html": ".html",
    "application/json": ".json",
    "text/csv": ".csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/xml": ".xml",
    "text/xml": ".xml",
    "application/x-yaml": ".yaml",
    "text/yaml": ".yaml",
}

EXTENSION_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".py": "text/x-python",
    ".js": "text/javascript",
    ".jsx": "text/javascript",
    ".ts": "text/typescript",
    ".tsx": "text/typescript",
    ".json": "application/json",
    ".html": "text/html",
    ".htm": "text/html",
    ".xml": "application/xml",
    ".yaml": "application/x-yaml",
    ".yml": "application/x-yaml",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    **{extension: mime_type for mime_type, extension in IMAGE_MIME_TO_EXTENSION.items()},
}

TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".html",
    ".htm",
    ".xml",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class AttachmentType:
    kind: str
    mime_type: str
    extension: str


def resolve_attachment_type(filename: str, content_type: str) -> AttachmentType:
    normalized_name = filename.strip()
    extension = Path(normalized_name).suffix.lower()
    normalized_content_type = content_type.split(";", 1)[0].strip().lower()

    if normalized_content_type in IMAGE_MIME_TO_EXTENSION:
        return AttachmentType(
            kind="image",
            mime_type=normalized_content_type,
            extension=IMAGE_MIME_TO_EXTENSION[normalized_content_type],
        )

    if normalized_content_type in DOCUMENT_MIME_TO_EXTENSION:
        return AttachmentType(
            kind="file",
            mime_type=normalized_content_type,
            extension=DOCUMENT_MIME_TO_EXTENSION[normalized_content_type],
        )

    if extension in EXTENSION_TO_MIME:
        resolved_mime = EXTENSION_TO_MIME[extension]
        kind = "image" if resolved_mime in IMAGE_MIME_TO_EXTENSION else "file"
        return AttachmentType(kind=kind, mime_type=resolved_mime, extension=extension)

    raise ValueError(
        "Unsupported attachment type. Supported files: images, PDF, text/markdown/code, CSV/XLSX, and DOCX."
    )


def is_image_attachment(mime_type: str) -> bool:
    return mime_type.split(";", 1)[0].strip().lower() in IMAGE_MIME_TO_EXTENSION


def is_text_attachment(extension: str) -> bool:
    return extension.lower() in TEXT_EXTENSIONS
