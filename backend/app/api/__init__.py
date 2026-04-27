from .auth import router as auth_router
from .audio import router as audio_router
from .chat import router as chat_router
from .conversations import router as conversations_router
from .images import router as images_router
from .knowledge import router as knowledge_router
from .memories import router as memories_router
from .models import router as models_router
from .debate import router as debate_router

__all__ = [
    "auth_router",
    "audio_router",
    "chat_router",
    "conversations_router",
    "debate_router",
    "images_router",
    "knowledge_router",
    "memories_router",
    "models_router",
]
