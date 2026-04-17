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
from .claude_client import list_claude_models
from .gemini_client import list_gemini_models
from .ollama_client import list_ollama_models
from .openai_client import list_codex_models, list_openai_local_models, list_openai_models, list_trio_models
from .registry import build_model_options
from .service import complete_chat, stream_chat
from .catalog import (
    uses_claude_native_multimodal,
    resolve_native_multimodal_mode,
    uses_codex_native_multimodal,
    uses_gemini_native_multimodal,
    uses_local_native_multimodal,
    uses_native_multimodal,
)

__all__ = [
    "DiscoveredModel",
    "ModelOption",
    "NativeMultimodalMode",
    "Provider",
    "build_model_options",
    "complete_chat",
    "list_claude_models",
    "list_codex_models",
    "list_gemini_models",
    "list_ollama_models",
    "list_openai_local_models",
    "list_openai_models",
    "list_trio_models",
    "model_provider_and_name",
    "namespaced_model",
    "normalize_model",
    "present_model_name",
    "resolve_native_multimodal_mode",
    "stream_chat",
    "uses_claude_native_multimodal",
    "uses_codex_native_multimodal",
    "uses_gemini_native_multimodal",
    "uses_local_native_multimodal",
    "uses_native_multimodal",
]
