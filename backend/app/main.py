from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import (
    audio_router,
    auth_router,
    battle_router,
    chat_router,
    conversations_router,
    debate_router,
    images_router,
    knowledge_router,
    memories_router,
    models_router,
)
from .audio import build_audio_services
from .cache import close_cache, initialize_cache
from .chat.state import build_chat_services
from .core.config import settings
from .core.http import shared_http_clients
from .core.logging import configure_logging
from .providers import ModelCatalogError, validate_model_catalog
from .runtime.chat_runs import ChatRunRegistry
from .runtime.debate_runs import DebateRunRegistry
from .storage.database import initialize_storage
from .storage.media import MEDIA_ROOT


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title=settings.app_name)
    app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")
    app.state.chat_services = build_chat_services(settings)
    app.state.audio_services = build_audio_services(settings)
    app.state.chat_run_registry = ChatRunRegistry()
    app.state.debate_run_registry = DebateRunRegistry()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def on_startup() -> None:
        try:
            validate_model_catalog()
        except ModelCatalogError as exc:
            raise RuntimeError(f"Model catalog validation failed: {exc}") from exc
        initialize_storage()
        await initialize_cache(settings)

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await shared_http_clients.aclose()
        await close_cache()

    app.include_router(auth_router)
    app.include_router(models_router)
    app.include_router(battle_router)
    app.include_router(knowledge_router)
    app.include_router(images_router)
    app.include_router(memories_router)
    app.include_router(conversations_router)
    app.include_router(debate_router)
    app.include_router(chat_router)
    app.include_router(audio_router)
    return app


app = create_app()
