from __future__ import annotations

from fastapi import APIRouter

from ..core.config import settings
from ..llm import (
    build_model_options,
    list_ollama_models,
    list_openai_local_models,
    list_openai_models,
    normalize_model,
)
from ..llm.catalog import list_catalog_discovered_models

router = APIRouter(tags=["system"])


@router.get("/api/health")
async def healthcheck():
    return {"status": "ok"}


@router.get("/api/models")
async def list_models():
    default_model = normalize_model(settings.default_model)
    catalog_models = list_catalog_discovered_models()

    if catalog_models:
        discovered_models = catalog_models
    else:
        ollama_models = await list_ollama_models()
        openai_models = await list_openai_models()
        openai_local_models = await list_openai_local_models()
        discovered_models = [*ollama_models, *openai_models, *openai_local_models]

    return {
        "models": build_model_options(discovered_models),
        "default_model": default_model,
    }
