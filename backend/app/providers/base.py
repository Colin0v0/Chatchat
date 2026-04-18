from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from ..chat.types import ChatMessagePayload
from ..runtime.events import CanonicalEvent
from .catalog import ModelProfile, ReasoningProfile


@dataclass(frozen=True)
class ProviderStreamRequest:
    profile: ModelProfile
    messages: list[ChatMessagePayload]
    reasoning_profile: ReasoningProfile


class ProviderAdapter(ABC):
    family: str

    @abstractmethod
    async def stream(self, request: ProviderStreamRequest) -> AsyncIterator[CanonicalEvent]:
        raise NotImplementedError
