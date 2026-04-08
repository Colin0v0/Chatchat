from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ..llm.catalog import resolve_model_route
from ..llm.openai_client import upload_openai_file
from ..storage.media import MEDIA_ROOT
from ..storage.models import MessageAttachment


async def ensure_upstream_file_id(*, db: Session, model: str, attachment: MessageAttachment) -> str:
    cached = (attachment.upstream_file_id or "").strip()
    if cached:
        return cached

    route = resolve_model_route(model)
    if route is None or not route.get("use_upstream_service"):
        raise RuntimeError(f"Model does not support upstream attachment service: {model}")

    file_id = await upload_openai_file(
        filename=attachment.original_name,
        mime_type=attachment.mime_type,
        file_path=MEDIA_ROOT / Path(attachment.relative_path),
        provider=route["provider"],
        base_url_override=route.get("upstream_service_base_url") or route.get("base_url"),
        api_key_override=route.get("api_key"),
    )
    attachment.upstream_file_id = file_id
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return file_id
