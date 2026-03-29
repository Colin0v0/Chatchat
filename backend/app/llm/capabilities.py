from __future__ import annotations

from typing import Literal, TypedDict

from ..core.config import settings

Provider = Literal["ollama", "openai"]


class DiscoveredModel(TypedDict):
    id: str
    supports_image_input: bool


class ModelOption(TypedDict):
    id: str
    label: str
    supports_thinking: bool
    supports_thinking_trace: bool
    supports_image_input: bool
    supports_image_upload: bool
    chat_model: str | None
    reasoning_model: str | None


EMBEDDING_MODEL_HINTS = (
    "embed",
    "embedding",
    "nomic-embed",
    "mxbai-embed",
    "bge-",
    "e5-",
)
NON_CHAT_MODEL_HINTS = (
    "translategemma",
    "translation",
)
OLLAMA_CAPABILITY_CACHE: dict[str, set[str]] = {}


def normalize_base_url(url: str) -> str:
    return url.rstrip("/")


def parse_csv_allowlist(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_openai_allowlist() -> list[str]:
    return parse_csv_allowlist(settings.openai_model_allowlist)


def parse_openai_vision_allowlist() -> set[str]:
    return set(parse_csv_allowlist(settings.openai_vision_model_allowlist))


def is_embedding_model_name(model_name: str) -> bool:
    normalized = model_name.strip().lower()
    return any(hint in normalized for hint in EMBEDDING_MODEL_HINTS)


def is_non_chat_model_name(model_name: str) -> bool:
    normalized = model_name.strip().lower()
    return any(hint in normalized for hint in NON_CHAT_MODEL_HINTS)


def filter_chat_model_names(model_names: list[str]) -> list[str]:
    return [
        name
        for name in model_names
        if not is_embedding_model_name(name) and not is_non_chat_model_name(name)
    ]


def model_provider_and_name(model: str) -> tuple[Provider, str]:
    parts = model.split(":", 1)
    if len(parts) == 2 and parts[0] in ("ollama", "openai") and parts[1].strip():
        return parts[0], parts[1].strip()
    if len(parts) == 2 and parts[0] not in ("ollama", "openai"):
        return "ollama", model

    if settings.default_provider == "openai":
        return "openai", model
    return "ollama", model


def namespaced_model(provider: Provider, model_name: str) -> str:
    return f"{provider}:{model_name}"


def normalize_model(model: str) -> str:
    provider, model_name = model_provider_and_name(model)
    return namespaced_model(provider, model_name)


def present_model_name(model: str) -> str:
    provider, model_name = model_provider_and_name(model)
    if provider in ("ollama", "openai"):
        return model_name
    return model


def supports_native_image_input(model: str) -> bool:
    provider, model_name = model_provider_and_name(model)
    if provider == "openai":
        return model_name in parse_openai_vision_allowlist()
    return "vision" in OLLAMA_CAPABILITY_CACHE.get(model_name, set())
