from __future__ import annotations

from typing import Any

from .base import ModeStream, RuntimeMode, UnsupportedModeActionError
from .debate_actions import (
    debate_ask_event_stream,
    debate_decision_event_stream,
    debate_next_event_stream,
)


class DebateRuntimeMode(RuntimeMode):
    mode_name = "debate"
    supported_actions = frozenset({"next", "ask", "decision"})

    def stream(self, action: str, /, **kwargs: Any) -> ModeStream:
        if action == "next":
            return debate_next_event_stream(**kwargs)
        if action == "ask":
            return debate_ask_event_stream(**kwargs)
        if action == "decision":
            return debate_decision_event_stream(**kwargs)
        raise UnsupportedModeActionError(f"Unsupported action for debate mode: {action}")


debate_mode = DebateRuntimeMode()
