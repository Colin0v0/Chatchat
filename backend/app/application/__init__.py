from __future__ import annotations


def __getattr__(name: str):
    if name in {"chat_stream_response", "regenerate_chat_response", "stream_active_chat_response"}:
        from .chat import chat_stream_response, regenerate_chat_response, stream_active_chat_response

        exports = {
            "chat_stream_response": chat_stream_response,
            "regenerate_chat_response": regenerate_chat_response,
            "stream_active_chat_response": stream_active_chat_response,
        }
        return exports[name]

    if name in {
        "advance_debate_session_response",
        "ask_debate_judge_question_response",
        "create_debate_judge_decision_response",
        "stream_active_debate_session_response",
    }:
        from .debate import (
            advance_debate_session_response,
            ask_debate_judge_question_response,
            create_debate_judge_decision_response,
            stream_active_debate_session_response,
        )

        exports = {
            "advance_debate_session_response": advance_debate_session_response,
            "ask_debate_judge_question_response": ask_debate_judge_question_response,
            "create_debate_judge_decision_response": create_debate_judge_decision_response,
            "stream_active_debate_session_response": stream_active_debate_session_response,
        }
        return exports[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "chat_stream_response",
    "regenerate_chat_response",
    "stream_active_chat_response",
    "advance_debate_session_response",
    "ask_debate_judge_question_response",
    "create_debate_judge_decision_response",
    "stream_active_debate_session_response",
]
