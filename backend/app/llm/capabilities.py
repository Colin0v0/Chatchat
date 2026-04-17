from __future__ import annotations

from typing import Literal, TypedDict

from ..core.config import settings

Provider = Literal["ollama", "openai", "openai_local", "codex", "gemini", "trio", "claude"]
NativeMultimodalMode = Literal["false", "local", "codex", "gemini", "claude"]


class DiscoveredModel(TypedDict):
    id: str
    supports_thinking: bool
    native_multimodal: NativeMultimodalMode


class DiscoveredModelWithDisplayName(DiscoveredModel, total=False):
    display_name: str


class ModelOption(TypedDict):
    id: str
    label: str
    supports_thinking: bool
    supports_thinking_trace: bool
    supports_attachment_upload: bool
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
    "translation",
    "translate",
)
OLLAMA_CAPABILITY_CACHE: dict[str, set[str]] = {}


def normalize_base_url(url: str) -> str:
    normalized = url.strip()
    if not normalized:
        raise ValueError("Base URL cannot be empty.")
    if normalized.startswith(":"):
        normalized = f"http://127.0.0.1{normalized}"
    elif "://" not in normalized:
        normalized = f"http://{normalized.lstrip('/')}"
    return normalized.rstrip("/")


def parse_csv_allowlist(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_openai_allowlist(provider: Provider = "openai") -> list[str]:
    if provider == "openai_local":
        return parse_csv_allowlist(settings.openai_local_model_allowlist)
    if provider == "codex":
        return parse_csv_allowlist(settings.codex_model_allowlist)
    if provider == "trio":
        return parse_csv_allowlist(settings.trio_model_allowlist)
    if provider == "claude":
        return parse_csv_allowlist(settings.claude_model_allowlist)
    return parse_csv_allowlist(settings.openai_model_allowlist)


def parse_gemini_allowlist() -> list[str]:
    return parse_csv_allowlist(settings.gemini_model_allowlist)


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
    if len(parts) == 2 and parts[0] in ("ollama", "openai", "openai_local", "codex", "gemini", "trio", "claude") and parts[1].strip():
        return parts[0], parts[1].strip()
    if len(parts) == 2 and parts[0] not in ("ollama", "openai", "openai_local", "codex", "gemini", "trio", "claude"):
        return "ollama", model

    if settings.default_provider in ("openai", "openai_local", "codex", "gemini", "trio", "claude"):
        return settings.default_provider, model
    return "ollama", model


def namespaced_model(provider: Provider, model_name: str) -> str:
    return f"{provider}:{model_name}"


def normalize_model(model: str) -> str:
    provider, model_name = model_provider_and_name(model)
    return namespaced_model(provider, model_name)


def present_model_name(model: str) -> str:
    provider, model_name = model_provider_and_name(model)
    if provider in ("ollama", "openai", "codex", "gemini", "trio", "claude"):
        return model_name
    return model
