from __future__ import annotations

from app.application import streaming


async def _fake_stream():
    yield '{"type":"done"}\n'


def test_stream_mode_action_wraps_runtime_stream(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeRuntime:
        def stream(self, action: str, /, *, request=None):
            captured["action"] = action
            captured["request"] = request
            return _fake_stream()

    def fake_get_mode_runtime(mode_name: str):
        captured["mode_name"] = mode_name
        return _FakeRuntime()

    request = object()
    monkeypatch.setattr(streaming, "get_mode_runtime", fake_get_mode_runtime)

    response = streaming.stream_mode_action(
        mode_name="chat",
        action="run",
        request=request,
    )

    assert response.media_type == "application/x-ndjson"
    assert captured["mode_name"] == "chat"
    assert captured["action"] == "run"
    assert captured["request"] is request
