from importlib import import_module

from .capabilities import (
    DiscoveredModel,
    ModelOption,
    NativeMultimodalMode,
    Provider,
    model_provider_and_name,
    namespaced_model,
    normalize_model,
    present_model_name,
)

_LAZY_EXPORTS = {
    "build_model_options": ("..providers", "build_model_options"),
    "list_claude_models": ("..provider_transports.anthropic", "list_claude_models"),
    "list_codex_models": ("..provider_transports.openai", "list_codex_models"),
    "list_gemini_models": ("..provider_transports.gemini", "list_gemini_models"),
    "list_openai_models": ("..provider_transports.openai", "list_openai_models"),
    "list_trio_models": ("..provider_transports.openai", "list_trio_models"),
    "resolve_native_multimodal_mode": ("..providers", "resolve_native_multimodal_mode"),
    "uses_claude_native_multimodal": ("..providers", "uses_claude_native_multimodal"),
    "uses_codex_native_multimodal": ("..providers", "uses_codex_native_multimodal"),
    "uses_gemini_native_multimodal": ("..providers", "uses_gemini_native_multimodal"),
    "uses_native_multimodal": ("..providers", "uses_native_multimodal"),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _LAZY_EXPORTS[name]
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value

__all__ = [
    "DiscoveredModel",
    "ModelOption",
    "NativeMultimodalMode",
    "Provider",
    "build_model_options",
    "list_claude_models",
    "list_codex_models",
    "list_gemini_models",
    "list_openai_models",
    "list_trio_models",
    "model_provider_and_name",
    "namespaced_model",
    "normalize_model",
    "present_model_name",
    "resolve_native_multimodal_mode",
    "uses_claude_native_multimodal",
    "uses_codex_native_multimodal",
    "uses_gemini_native_multimodal",
    "uses_native_multimodal",
]
