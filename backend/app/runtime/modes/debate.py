from __future__ import annotations

from ..requests import DebateAskRequest, DebateDecisionRequest, DebateNextRequest, ModeActionRequest
from .base import ModeStream, RuntimeMode
from .debate_actions import (
    debate_ask_event_stream,
    debate_decision_event_stream,
    debate_next_event_stream,
)


class DebateRuntimeMode(RuntimeMode):
    mode_name = "debate"
    supported_actions = frozenset({"next", "ask", "decision"})

    def stream(self, action: str, /, *, request: ModeActionRequest | None = None) -> ModeStream:
        self.ensure_supported_action(action)
        if action == "next":
            debate_request = self.require_request(request, DebateNextRequest)
            return debate_next_event_stream(
                db=debate_request.db,
                request=debate_request.request,
                session=debate_request.session,
            )
        if action == "ask":
            debate_request = self.require_request(request, DebateAskRequest)
            return debate_ask_event_stream(
                db=debate_request.db,
                request=debate_request.request,
                session=debate_request.session,
                payload=debate_request.payload,
            )
        debate_request = self.require_request(request, DebateDecisionRequest)
        return debate_decision_event_stream(
            db=debate_request.db,
            request=debate_request.request,
            session=debate_request.session,
            payload=debate_request.payload,
        )


debate_mode = DebateRuntimeMode()
