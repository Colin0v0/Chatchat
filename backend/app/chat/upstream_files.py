from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from ..providers import resolve_model_profile
from ..provider_transports.openai import upload_openai_file
from ..storage.media import MEDIA_ROOT
from ..storage.models import MessageAttachment, ProviderFileRef


def _base_url_hash(value: str) -> str:
    return hashlib.sha256(value.strip().lower().rstrip("/").encode("utf-8")).hexdigest()


async def ensure_upstream_file_id(*, db: Session, model: str, attachment: MessageAttachment) -> str:
    profile = resolve_model_profile(model)
    if profile is None or profile.provider_family != "openai" or not profile.file_base_url:
        raise RuntimeError(f"Model is not configured for native multimodal uploads: {model}")
    cache_key = _base_url_hash(profile.file_base_url)
    cached_ref = next(
        (
            ref
            for ref in attachment.provider_file_refs
            if ref.provider_family == profile.provider_family and ref.base_url_hash == cache_key
        ),
        None,
    )
    if cached_ref is not None and cached_ref.remote_file_id.strip():
        return cached_ref.remote_file_id

    file_id = await upload_openai_file(
        filename=attachment.original_name,
        mime_type=attachment.mime_type,
        file_path=MEDIA_ROOT / Path(attachment.relative_path),
        provider=profile.provider_name,  # type: ignore[arg-type]
        base_url_override=profile.file_base_url,
        api_key_override=profile.api_key,
    )
    provider_file_ref = ProviderFileRef(
        attachment_id=attachment.id,
        provider_family=profile.provider_family,
        base_url_hash=cache_key,
        remote_file_id=file_id,
        remote_purpose="user_data",
    )
    db.add(provider_file_ref)
    db.commit()
    db.refresh(provider_file_ref)
    return file_id
