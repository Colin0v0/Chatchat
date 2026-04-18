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


def test_chat_mode_requires_structured_run_request():
    chat_mode = get_mode_runtime("chat")

    try:
        chat_mode.stream("run")
    except ValueError as exc:
        assert "ChatRunRequest" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError")


def test_debate_mode_requires_structured_next_request():
    debate_mode = get_mode_runtime("debate")

    try:
        debate_mode.stream("next")
    except ValueError as exc:
        assert "DebateNextRequest" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError")


def test_debate_mode_requires_structured_ask_request():
    debate_mode = get_mode_runtime("debate")

    try:
        debate_mode.stream("ask")
    except ValueError as exc:
        assert "DebateAskRequest" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError")


def test_debate_mode_requires_structured_decision_request():
    debate_mode = get_mode_runtime("debate")

    try:
        debate_mode.stream("decision")
    except ValueError as exc:
        assert "DebateDecisionRequest" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError")
