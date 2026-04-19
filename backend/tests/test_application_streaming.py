from __future__ import annotations

from app.application import streaming
from app.runtime import streaming as runtime_streaming


async def _fake_stream():
    yield '{"type":"done"}\n'


def test_stream_mode_action_delegates_to_runtime_response(monkeypatch):
    captured: dict[str, object] = {}

    request = object()
    expected_response = object()

    def fake_stream_mode_response(*, mode_name: str, action: str, request):
        captured["mode_name"] = mode_name
        captured["action"] = action
        captured["request"] = request
        return expected_response

    monkeypatch.setattr(streaming, "stream_mode_response", fake_stream_mode_response)

    response = streaming.stream_mode_action(
        mode_name="chat",
        action="run",
        request=request,
    )

    assert response is expected_response
    assert captured["mode_name"] == "chat"
    assert captured["action"] == "run"
    assert captured["request"] is request


def test_runtime_stream_mode_response_wraps_mode_stream(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeRuntime:
        def stream(self, action: str, /, *, request=None):
            captured["action"] = action
            captured["request"] = request
            return _fake_stream()

    def fake_resolve_mode_runtime(mode_name: str):
        captured["mode_name"] = mode_name
        return _FakeRuntime()

    request = object()
    monkeypatch.setattr(runtime_streaming, "resolve_mode_runtime", fake_resolve_mode_runtime)

    response = runtime_streaming.stream_mode_response(
        mode_name="chat",
        action="run",
        request=request,
    )

    assert response.media_type == runtime_streaming.NDJSON_MEDIA_TYPE
    assert captured["mode_name"] == "chat"
    assert captured["action"] == "run"
    assert captured["request"] is request
