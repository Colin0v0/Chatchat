from __future__ import annotations

from fastapi import APIRouter

from ..core.config import settings
from ..llm import build_model_options, list_ollama_models, list_openai_models, normalize_model

router = APIRouter(tags=["system"])


@router.get("/api/health")
async def healthcheck():
    return {"status": "ok"}


@router.get("/api/models")
async def list_models():
    ollama_models = await list_ollama_models()
    openai_models = await list_openai_models()
    default_model = normalize_model(settings.default_model)

    return {
        "models": build_model_options([*ollama_models, *openai_models]),
        "default_model": default_model,
    }
