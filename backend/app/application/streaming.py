from __future__ import annotations

from fastapi.responses import StreamingResponse

from ..runtime.modes import get_mode_runtime
from ..runtime.requests import ModeActionRequest


def stream_mode_action(
    *,
    mode_name: str,
    action: str,
    request: ModeActionRequest,
) -> StreamingResponse:
    runtime = get_mode_runtime(mode_name)
    return StreamingResponse(
        runtime.stream(action, request=request),
        media_type="application/x-ndjson",
    )
