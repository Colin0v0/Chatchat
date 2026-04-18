from __future__ import annotations

from fastapi import APIRouter, Depends

from ..auth import require_current_user
from ..core.config import settings
from ..providers import build_model_options, normalize_model

router = APIRouter(tags=["system"])


@router.get("/api/health")
async def healthcheck():
    return {"status": "ok"}


@router.get("/api/models")
async def list_models(_=Depends(require_current_user)):
    default_model = normalize_model(settings.default_model)
    return {
        "models": build_model_options(),
        "default_model": default_model,
    }
