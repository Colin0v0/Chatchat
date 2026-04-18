from .events import CanonicalEvent


def __getattr__(name: str):
    if name == "stream_chat_run":
        from .orchestrator import stream_chat_run

        return stream_chat_run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "CanonicalEvent",
    "stream_chat_run",
]
