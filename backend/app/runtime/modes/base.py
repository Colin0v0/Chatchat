from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

ModeStream = AsyncIterator[str]


class UnsupportedModeActionError(LookupError):
    pass


class RuntimeMode(Protocol):
    mode_name: str
    supported_actions: frozenset[str]

    def stream(self, action: str, /, **kwargs: Any) -> ModeStream:
        ...
