from __future__ import annotations

from typing import Any

from ..orchestrator import stream_chat_run
from .base import ModeStream, RuntimeMode, UnsupportedModeActionError


class ChatRuntimeMode(RuntimeMode):
    mode_name = "chat"
    supported_actions = frozenset({"run"})

    def stream(self, action: str, /, **kwargs: Any) -> ModeStream:
        if action != "run":
            raise UnsupportedModeActionError(f"Unsupported action for chat mode: {action}")
        return stream_chat_run(**kwargs)


chat_mode = ChatRuntimeMode()
