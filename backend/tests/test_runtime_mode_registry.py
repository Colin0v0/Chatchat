from app.runtime.modes import get_mode_runtime, list_mode_runtimes
from app.runtime.modes.base import UnsupportedModeActionError


def test_lists_builtin_mode_runtimes():
    modes = {mode.mode_name: mode for mode in list_mode_runtimes()}

    assert set(modes) == {"chat", "debate"}
    assert modes["chat"].supported_actions == {"run"}
    assert modes["debate"].supported_actions == {"next", "ask", "decision"}


def test_chat_mode_rejects_unknown_action():
    chat_mode = get_mode_runtime("chat")

    try:
        chat_mode.stream("unknown")
    except UnsupportedModeActionError as exc:
        assert "chat mode" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected UnsupportedModeActionError")


def test_debate_mode_rejects_unknown_action():
    debate_mode = get_mode_runtime("debate")

    try:
        debate_mode.stream("unknown")
    except UnsupportedModeActionError as exc:
        assert "debate mode" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected UnsupportedModeActionError")
