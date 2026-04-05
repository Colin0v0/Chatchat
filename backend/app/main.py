from __future__ import annotations

from threading import Lock

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import audio_router, chat_router, conversations_router, memories_router, models_router, rag_router
from .audio import build_audio_services
from .chat.state import build_chat_services
from .core.config import settings
from .core.logging import configure_logging
from .storage.database import Base, engine, ensure_schema
from .storage.media import MEDIA_ROOT


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title=settings.app_name)
    app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")
    local_gpu_lock = Lock()
    app.state.chat_services = build_chat_services(settings, local_gpu_lock=local_gpu_lock)
    app.state.audio_services = build_audio_services(settings, local_gpu_lock=local_gpu_lock)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def on_startup() -> None:
        Base.metadata.create_all(bind=engine)
        ensure_schema()

    app.include_router(models_router)
    app.include_router(rag_router)
    app.include_router(memories_router)
    app.include_router(conversations_router)
    app.include_router(chat_router)
    app.include_router(audio_router)
    return app


app = create_app()
