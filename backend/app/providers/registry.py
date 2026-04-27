from __future__ import annotations

from .anthropic_family import AnthropicProviderAdapter
from .base import ProviderAdapter
from .gemini_family import GeminiProviderAdapter
from .openai_family import OpenAIProviderAdapter


class ProviderRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, ProviderAdapter] = {
            "openai": OpenAIProviderAdapter(),
            "anthropic": AnthropicProviderAdapter(),
            "gemini": GeminiProviderAdapter(),
        }

    def get(self, family: str) -> ProviderAdapter:
        adapter = self._adapters.get(family)
        if adapter is None:
            raise ValueError(f"Unsupported provider family: {family}")
        return adapter


provider_registry = ProviderRegistry()
