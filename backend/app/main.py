from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import chat_router, conversations_router, models_router, rag_router
from .chat import build_chat_services
from .core.config import settings
from .storage import Base, MEDIA_ROOT, engine, ensure_schema


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.mount("/media", StaticFiles(directory=MEDIA_ROOT), name="media")
    app.state.chat_services = build_chat_services(settings)

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
    app.include_router(conversations_router)
    app.include_router(chat_router)
    return app


app = create_app()
