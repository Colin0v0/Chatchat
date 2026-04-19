from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from .requests import ModeActionRequest

NDJSON_MEDIA_TYPE = "application/x-ndjson"


def ndjson_stream_response(stream: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type=NDJSON_MEDIA_TYPE,
    )


def resolve_mode_runtime(mode_name: str):
    from .modes import get_mode_runtime

    return get_mode_runtime(mode_name)


def stream_mode_response(
    *,
    mode_name: str,
    action: str,
    request: ModeActionRequest,
) -> StreamingResponse:
    runtime = resolve_mode_runtime(mode_name)
    return ndjson_stream_response(runtime.stream(action, request=request))
