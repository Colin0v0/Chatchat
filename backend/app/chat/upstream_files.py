from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..core.config import settings
from ..llm.catalog import resolve_model_route
from ..llm.openai_client import upload_openai_file
from ..storage.media import MEDIA_ROOT
from ..storage.models import MessageAttachment


async def ensure_upstream_file_id(*, db: Session, model: str, attachment: MessageAttachment) -> str:
    cached = (attachment.upstream_file_id or "").strip()
    if cached:
        return cached

    route = resolve_model_route(model)
    if route is None or not route.get("native_multimodal"):
        raise RuntimeError(f"Model is not configured for native multimodal uploads: {model}")
    upload_base_url = route.get("upstream_service_base_url")
    if route["provider"] == "openai_local" and not upload_base_url:
        upload_base_url = settings.openai_local_upstream_service_base_url.strip() or None
    if not upload_base_url:
        raise RuntimeError(f"Native multimodal upload endpoint is not configured for model: {model}")

    file_id = await upload_openai_file(
        filename=attachment.original_name,
        mime_type=attachment.mime_type,
        file_path=MEDIA_ROOT / Path(attachment.relative_path),
        provider=route["provider"],
        base_url_override=upload_base_url,
        api_key_override=route.get("api_key"),
    )
    attachment.upstream_file_id = file_id
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return file_id
