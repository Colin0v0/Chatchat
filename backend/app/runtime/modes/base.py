from __future__ import annotations

from collections.abc import AsyncIterator
from abc import ABC, abstractmethod
from typing import TypeVar

from ..requests import ModeActionRequest

ModeStream = AsyncIterator[str]
ModeRequest = TypeVar("ModeRequest", bound=ModeActionRequest)


class UnsupportedModeActionError(LookupError):
    pass


class RuntimeMode(ABC):
    mode_name: str
    supported_actions: frozenset[str]

    def ensure_supported_action(self, action: str) -> None:
        if action not in self.supported_actions:
            raise UnsupportedModeActionError(
                f"Unsupported action for {self.mode_name} mode: {action}"
            )

    def require_request(
        self,
        request: ModeActionRequest | None,
        expected_type: type[ModeRequest],
    ) -> ModeRequest:
        if isinstance(request, expected_type):
            return request
        raise ValueError(
            f"{self.mode_name.title()} mode action requires {expected_type.__name__}."
        )

    @abstractmethod
    def stream(self, action: str, /, *, request: ModeActionRequest | None = None) -> ModeStream:
        raise NotImplementedError
