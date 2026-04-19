from __future__ import annotations

from fastapi.responses import StreamingResponse

from ..runtime.streaming import stream_mode_response
from ..runtime.requests import ModeActionRequest


def stream_mode_action(
    *,
    mode_name: str,
    action: str,
    request: ModeActionRequest,
) -> StreamingResponse:
    return stream_mode_response(
        mode_name=mode_name,
        action=action,
        request=request,
    )
