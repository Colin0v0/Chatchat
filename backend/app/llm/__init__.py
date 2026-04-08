from .capabilities import (
    DiscoveredModel,
    ModelOption,
    Provider,
    model_provider_and_name,
    namespaced_model,
    normalize_model,
    present_model_name,
)
from .ollama_client import list_ollama_models
from .openai_client import list_openai_local_models, list_openai_models
from .registry import build_model_options
from .service import complete_chat, stream_chat
from .catalog import uses_native_multimodal

__all__ = [
    "DiscoveredModel",
    "ModelOption",
    "Provider",
    "build_model_options",
    "complete_chat",
    "list_ollama_models",
    "list_openai_local_models",
    "list_openai_models",
    "model_provider_and_name",
    "namespaced_model",
    "normalize_model",
    "present_model_name",
    "stream_chat",
    "uses_native_multimodal",
]
