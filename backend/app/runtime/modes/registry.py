from __future__ import annotations

from .base import RuntimeMode
from .chat import chat_mode
from .debate import debate_mode


class ModeRegistry:
    def __init__(self, *modes: RuntimeMode):
        self._modes: dict[str, RuntimeMode] = {}
        for mode in modes:
            self.register(mode)

    def register(self, mode: RuntimeMode) -> None:
        self._modes[mode.mode_name] = mode

    def get(self, mode_name: str) -> RuntimeMode:
        try:
            return self._modes[mode_name]
        except KeyError as exc:
            raise LookupError(f"Unknown runtime mode: {mode_name}") from exc

    def list_modes(self) -> tuple[RuntimeMode, ...]:
        return tuple(self._modes.values())


mode_registry = ModeRegistry(chat_mode, debate_mode)


def get_mode_runtime(mode_name: str) -> RuntimeMode:
    return mode_registry.get(mode_name)


def list_mode_runtimes() -> tuple[RuntimeMode, ...]:
    return mode_registry.list_modes()
