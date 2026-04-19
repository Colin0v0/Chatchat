from __future__ import annotations

from ..orchestrator import stream_chat_run
from ..requests import ChatRunRequest, ModeActionRequest
from .base import ModeStream, RuntimeMode


class ChatRuntimeMode(RuntimeMode):
    mode_name = "chat"
    supported_actions = frozenset({"run"})

    def stream(self, action: str, /, *, request: ModeActionRequest | None = None) -> ModeStream:
        self.ensure_supported_action(action)
        chat_request = self.require_request(request, ChatRunRequest)
        return stream_chat_run(
            services=chat_request.services,
            request=chat_request.request,
            conversation_id=chat_request.conversation_id,
            message_id=chat_request.message_id,
            model=chat_request.model,
            history_message_ids=chat_request.history_message_ids,
            query=chat_request.query,
            tool_policy=chat_request.tool_policy,
            requested_reasoning=chat_request.requested_reasoning,
            requested_reasoning_profile=chat_request.requested_reasoning_profile,
        )


chat_mode = ChatRuntimeMode()
