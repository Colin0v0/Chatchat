from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from ..core.config import BASE_DIR, settings
from ..llm.capabilities import (
    NativeMultimodalMode,
    Provider,
    model_provider_and_name,
    normalize_model as normalize_model_id,
    present_model_name,
)

logger = logging.getLogger("chatchat.model_catalog")

ReasoningProfile = Literal["off", "auto", "low", "medium", "high", "max", "provider_default"]
ReasoningControl = Literal["none", "toggle", "effort", "budget", "prompt_tag"]
ReasoningVisibility = Literal["none", "summary", "full"]
ReasoningContinuation = Literal["none", "stateful", "signature"]


class ModelCatalogError(RuntimeError):
    pass


@dataclass(frozen=True)
class CapabilityMatrix:
    input_text: bool
    input_image: bool
    input_pdf: bool
    input_other_file: bool
    input_audio: bool
    transport_inline_data: bool
    transport_file_upload: bool
    transport_remote_url: bool
    reasoning_control: ReasoningControl
    reasoning_profiles: tuple[ReasoningProfile, ...]
    reasoning_visibility: ReasoningVisibility
    reasoning_continuation: ReasoningContinuation
    reasoning_visible_trace: bool
    reasoning_summary_only: bool
    tools_function_calling: bool
    tools_parallel_calls: bool
    tools_forced_call: bool
    stream_text: bool
    stream_reasoning: bool
    stream_tool_call: bool
    stream_usage: bool
    state_previous_response: bool

    @property
    def supports_attachment_upload(self) -> bool:
        return self.input_image or self.input_pdf or self.input_other_file or self.input_audio


@dataclass(frozen=True)
class ModelProfile:
    id: str
    display_name: str
    provider_name: str
    provider_family: str
    upstream_model: str
    chat_base_url: str | None
    file_base_url: str | None
    api_key: str | None
    context_window: int | None
    native_multimodal_mode: NativeMultimodalMode
    supports_thinking: bool
    capabilities: CapabilityMatrix
    default_reasoning_profile: ReasoningProfile


@dataclass(frozen=True)
class ProviderPreset:
    provider: Provider | None
    base_url: str | None
    upstream_service_base_url: str | None
    api_key: str | None


def _provider_family(provider_name: str) -> str:
    if provider_name in {"openai", "openai_local", "codex", "trio"}:
        return "openai"
    if provider_name == "claude":
        return "anthropic"
    if provider_name == "gemini":
        return "gemini"
    return "ollama"


def _resolve_config_value(env_name: str) -> str | None:
    env_value = os.getenv(env_name, "").strip()
    if env_value:
        return env_value

    setting_name = env_name.strip().lower()
    if not setting_name or not hasattr(settings, setting_name):
        return None

    value = getattr(settings, setting_name)
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _resolve_catalog_path() -> Path:
    configured = Path(settings.model_catalog_path)
    if configured.is_absolute():
        return configured
    return BASE_DIR / configured


def _resolve_env_value(value: str | None) -> str | None:
    if not value:
        return None
    trimmed = value.strip()
    if trimmed.startswith("${") and trimmed.endswith("}"):
        env_name = trimmed[2:-1].strip()
        return _resolve_config_value(env_name)
    return trimmed


def _resolve_api_key(*, api_key: str | None, api_key_env: str | None) -> str | None:
    direct = (api_key or "").strip()
    if direct:
        return direct
    env_name = (api_key_env or "").strip()
    if not env_name:
        return None
    return _resolve_config_value(env_name)


def _normalize_provider(value: str | None, fallback_model_id: str) -> Provider:
    if value in {"ollama", "openai", "openai_local", "codex", "gemini", "trio", "claude"}:
        return cast(Provider, value)
    provider, _ = model_provider_and_name(fallback_model_id)
    return provider


def _normalize_reasoning_control(value: str) -> ReasoningControl:
    normalized = value.strip().lower()
    if normalized in {"none", "toggle", "effort", "budget", "prompt_tag"}:
        return cast(ReasoningControl, normalized)
    raise ModelCatalogError(
        "Invalid reasoning control. Expected one of: none, toggle, effort, budget, prompt_tag"
    )


def _normalize_reasoning_profile(value: str) -> ReasoningProfile:
    normalized = value.strip().lower()
    if normalized in {"off", "auto", "low", "medium", "high", "max", "provider_default"}:
        return cast(ReasoningProfile, normalized)
    raise ModelCatalogError(
        "Invalid reasoning default_profile. Expected one of: off, auto, low, medium, high, max, provider_default"
    )


def _normalize_reasoning_visibility(value: str) -> ReasoningVisibility:
    normalized = value.strip().lower()
    if normalized in {"none", "summary", "full"}:
        return cast(ReasoningVisibility, normalized)
    raise ModelCatalogError(
        "Invalid reasoning visibility. Expected one of: none, summary, full"
    )


def _normalize_reasoning_continuation(value: str) -> ReasoningContinuation:
    normalized = value.strip().lower()
    if normalized in {"none", "stateful", "signature"}:
        return cast(ReasoningContinuation, normalized)
    raise ModelCatalogError(
        "Invalid reasoning continuation. Expected one of: none, stateful, signature"
    )


def _normalize_native_multimodal_mode(value: str) -> NativeMultimodalMode:
    normalized = value.strip().lower()
    if normalized in {"false", "local", "codex", "gemini", "claude"}:
        return cast(NativeMultimodalMode, normalized)
    raise ModelCatalogError("Invalid runtime.native_multimodal_mode. Expected one of: false, local, codex, gemini, claude")


def _read_bool(raw: dict[str, object], key: str, path: str, *, default: bool = False) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ModelCatalogError(f"{path}.{key} must be boolean")
    return value


def _read_optional_int(raw: dict[str, object], key: str, path: str) -> int | None:
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ModelCatalogError(f"{path}.{key} must be a positive integer")
    return value


def _read_object(raw: dict[str, object], key: str, path: str) -> dict[str, object]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ModelCatalogError(f"{path}.{key} must be an object")
    return cast(dict[str, object], value)


def _read_optional_object(raw: dict[str, object], key: str, path: str) -> dict[str, object] | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ModelCatalogError(f"{path}.{key} must be an object when provided")
    return cast(dict[str, object], value)


def _read_optional_string(raw: dict[str, object], key: str, path: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ModelCatalogError(f"{path}.{key} must be string when provided")
    return value


def _read_optional_string_list(raw: dict[str, object], key: str, path: str) -> list[str] | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ModelCatalogError(f"{path}.{key} must be an array of strings when provided")
    return [item for item in cast(list[str], value)]


def _parse_provider_presets(payload: dict[str, object]) -> dict[str, ProviderPreset]:
    raw = payload.get("providers", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ModelCatalogError("model catalog 'providers' must be an object")

    presets: dict[str, ProviderPreset] = {}
    for name, item in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise ModelCatalogError("providers keys must be non-empty strings")
        if not isinstance(item, dict):
            raise ModelCatalogError(f"providers.{name} must be an object")

        provider_raw = _read_optional_string(item, "provider", f"providers.{name}")
        provider = _normalize_provider(provider_raw.strip(), "ollama:placeholder") if provider_raw and provider_raw.strip() else None

        endpoints = _read_optional_object(item, "endpoints", f"providers.{name}") or {}
        base_url = _resolve_env_value(_read_optional_string(endpoints, "chat", f"providers.{name}.endpoints"))
        file_base_url = _resolve_env_value(_read_optional_string(endpoints, "files", f"providers.{name}.endpoints"))

        legacy_base_url = _resolve_env_value(_read_optional_string(item, "base_url", f"providers.{name}"))
        legacy_file_base_url = _resolve_env_value(
            _read_optional_string(item, "upstream_service_base_url", f"providers.{name}")
        )
        resolved_api_key = _resolve_api_key(
            api_key=_read_optional_string(item, "api_key", f"providers.{name}"),
            api_key_env=_read_optional_string(item, "api_key_env", f"providers.{name}"),
        )

        presets[name.strip()] = ProviderPreset(
            provider=provider,
            base_url=base_url or legacy_base_url,
            upstream_service_base_url=file_base_url or legacy_file_base_url,
            api_key=resolved_api_key,
        )

    return presets


def _parse_capabilities(row: dict[str, object], row_path: str) -> tuple[CapabilityMatrix, ReasoningProfile]:
    capabilities_raw = _read_object(row, "capabilities", row_path)
    input_cfg = _read_object(capabilities_raw, "input", f"{row_path}.capabilities")
    transport_cfg = _read_object(capabilities_raw, "transport", f"{row_path}.capabilities")
    reasoning_cfg = _read_object(capabilities_raw, "reasoning", f"{row_path}.capabilities")
    tools_cfg = _read_object(capabilities_raw, "tools", f"{row_path}.capabilities")
    stream_cfg = _read_object(capabilities_raw, "stream", f"{row_path}.capabilities")
    state_cfg = _read_object(capabilities_raw, "state", f"{row_path}.capabilities")

    control_raw = _read_optional_string(reasoning_cfg, "control", f"{row_path}.capabilities.reasoning") or "none"
    default_profile_raw = (
        _read_optional_string(reasoning_cfg, "default_profile", f"{row_path}.capabilities.reasoning") or "off"
    )
    reasoning_control = _normalize_reasoning_control(control_raw)
    default_reasoning_profile = _normalize_reasoning_profile(default_profile_raw)
    supported_profiles_raw = _read_optional_string_list(
        reasoning_cfg,
        "supported_profiles",
        f"{row_path}.capabilities.reasoning",
    )
    visibility_raw = _read_optional_string(
        reasoning_cfg,
        "visibility",
        f"{row_path}.capabilities.reasoning",
    )
    continuation_raw = _read_optional_string(
        reasoning_cfg,
        "continuation",
        f"{row_path}.capabilities.reasoning",
    )

    if supported_profiles_raw is None:
        if reasoning_control == "none":
            reasoning_profiles: tuple[ReasoningProfile, ...] = ("off",)
        elif reasoning_control in {"toggle", "prompt_tag"}:
            reasoning_profiles = ("auto", "off", "medium")
        else:
            reasoning_profiles = ("auto", "off", "low", "medium", "high", "max")
    else:
        normalized_profiles = tuple(_normalize_reasoning_profile(item) for item in supported_profiles_raw)
        if not normalized_profiles:
            raise ModelCatalogError(
                f"{row_path}.capabilities.reasoning.supported_profiles cannot be empty"
            )
        reasoning_profiles = tuple(dict.fromkeys(normalized_profiles))

    if visibility_raw:
        reasoning_visibility = _normalize_reasoning_visibility(visibility_raw)
    elif reasoning_control == "none":
        reasoning_visibility = "none"
    elif _read_bool(reasoning_cfg, "summary_only", f"{row_path}.capabilities.reasoning"):
        reasoning_visibility = "summary"
    elif _read_bool(reasoning_cfg, "visible_trace", f"{row_path}.capabilities.reasoning"):
        reasoning_visibility = "full"
    else:
        reasoning_visibility = "none"

    if continuation_raw:
        reasoning_continuation = _normalize_reasoning_continuation(continuation_raw)
    elif reasoning_control == "none":
        reasoning_continuation = "none"
    else:
        reasoning_continuation = "stateful"

    matrix = CapabilityMatrix(
        input_text=_read_bool(input_cfg, "text", f"{row_path}.capabilities.input", default=True),
        input_image=_read_bool(input_cfg, "image", f"{row_path}.capabilities.input"),
        input_pdf=_read_bool(input_cfg, "pdf", f"{row_path}.capabilities.input"),
        input_other_file=_read_bool(input_cfg, "other_file", f"{row_path}.capabilities.input"),
        input_audio=_read_bool(input_cfg, "audio", f"{row_path}.capabilities.input"),
        transport_inline_data=_read_bool(transport_cfg, "inline_data", f"{row_path}.capabilities.transport"),
        transport_file_upload=_read_bool(transport_cfg, "file_upload", f"{row_path}.capabilities.transport"),
        transport_remote_url=_read_bool(transport_cfg, "remote_url", f"{row_path}.capabilities.transport"),
        reasoning_control=reasoning_control,
        reasoning_profiles=reasoning_profiles,
        reasoning_visibility=reasoning_visibility,
        reasoning_continuation=reasoning_continuation,
        reasoning_visible_trace=_read_bool(
            reasoning_cfg,
            "visible_trace",
            f"{row_path}.capabilities.reasoning",
        ),
        reasoning_summary_only=_read_bool(
            reasoning_cfg,
            "summary_only",
            f"{row_path}.capabilities.reasoning",
        ),
        tools_function_calling=_read_bool(tools_cfg, "function_calling", f"{row_path}.capabilities.tools"),
        tools_parallel_calls=_read_bool(tools_cfg, "parallel_calls", f"{row_path}.capabilities.tools"),
        tools_forced_call=_read_bool(tools_cfg, "forced_call", f"{row_path}.capabilities.tools"),
        stream_text=_read_bool(stream_cfg, "text", f"{row_path}.capabilities.stream", default=True),
        stream_reasoning=_read_bool(stream_cfg, "reasoning", f"{row_path}.capabilities.stream"),
        stream_tool_call=_read_bool(stream_cfg, "tool_call", f"{row_path}.capabilities.stream"),
        stream_usage=_read_bool(stream_cfg, "usage", f"{row_path}.capabilities.stream"),
        state_previous_response=_read_bool(state_cfg, "previous_response", f"{row_path}.capabilities.state"),
    )

    if matrix.reasoning_control == "none" and default_reasoning_profile != "off":
        raise ModelCatalogError(
            f"{row_path}.capabilities.reasoning.default_profile must be off when reasoning.control is none"
        )
    if matrix.reasoning_control == "none" and matrix.reasoning_profiles != ("off",):
        raise ModelCatalogError(
            f"{row_path}.capabilities.reasoning.supported_profiles must be ['off'] when reasoning.control is none"
        )
    if default_reasoning_profile == "provider_default" and "auto" not in matrix.reasoning_profiles:
        raise ModelCatalogError(
            f"{row_path}.capabilities.reasoning.supported_profiles must include auto when default_profile is provider_default"
        )
    if default_reasoning_profile != "provider_default" and default_reasoning_profile not in matrix.reasoning_profiles:
        raise ModelCatalogError(
            f"{row_path}.capabilities.reasoning.supported_profiles must include {default_reasoning_profile}"
        )
    return matrix, default_reasoning_profile


def _resolve_native_multimodal_from_profile(
    *,
    row: dict[str, object],
    row_path: str,
    provider_name: str,
    capabilities: CapabilityMatrix,
) -> NativeMultimodalMode:
    runtime_cfg = _read_optional_object(row, "runtime", row_path) or {}
    explicit_mode = _read_optional_string(runtime_cfg, "native_multimodal_mode", f"{row_path}.runtime")
    if explicit_mode:
        return _normalize_native_multimodal_mode(explicit_mode)
    if provider_name == "openai_local" and capabilities.transport_file_upload:
        return "local"
    if provider_name == "codex" and capabilities.transport_file_upload:
        return "codex"
    if provider_name == "gemini" and capabilities.transport_inline_data:
        return "gemini"
    if provider_name == "claude" and capabilities.transport_inline_data:
        return "claude"
    return "false"


def _parse_profiles(payload: dict[str, object]) -> list[ModelProfile]:
    presets = _parse_provider_presets(payload)
    rows = payload.get("models")
    if not isinstance(rows, list):
        raise ModelCatalogError("model catalog must contain a 'models' array")

    profiles: list[ModelProfile] = []
    seen_model_ids: set[str] = set()

    for index, row in enumerate(rows):
        row_path = f"models[{index}]"
        if not isinstance(row, dict):
            raise ModelCatalogError(f"{row_path} must be an object")

        model_id_raw = row.get("id")
        if not isinstance(model_id_raw, str) or not model_id_raw.strip():
            raise ModelCatalogError(f"{row_path}.id must be a non-empty string")
        model_id = normalize_model_id(model_id_raw.strip())
        if model_id in seen_model_ids:
            raise ModelCatalogError(f"Duplicate model id in catalog: {model_id}")
        seen_model_ids.add(model_id)

        enabled_raw = row.get("enabled", True)
        if not isinstance(enabled_raw, bool):
            raise ModelCatalogError(f"{row_path}.enabled must be boolean")
        if not enabled_raw:
            continue

        display_name_raw = _read_optional_string(row, "display_name", row_path)
        display_name = display_name_raw.strip() if isinstance(display_name_raw, str) else ""

        provider_ref = (_read_optional_string(row, "provider_ref", row_path) or "").strip()
        preset = presets.get(provider_ref) if provider_ref else None
        if provider_ref and preset is None:
            raise ModelCatalogError(f"{row_path}.provider_ref references unknown provider preset: {provider_ref}")

        provider_source = (_read_optional_string(row, "provider", row_path) or "").strip()
        if not provider_source and preset is not None and preset.provider:
            provider_source = preset.provider
        provider = _normalize_provider(provider_source or None, model_id)

        _, model_name = model_provider_and_name(model_id)
        upstream_model = _resolve_env_value(_read_optional_string(row, "upstream_model", row_path))
        upstream_model = upstream_model.strip() if isinstance(upstream_model, str) else ""
        if not upstream_model:
            upstream_model = model_name

        endpoints_cfg = _read_optional_object(row, "endpoints", row_path) or {}
        chat_base_url = _resolve_env_value(_read_optional_string(endpoints_cfg, "chat", f"{row_path}.endpoints"))
        file_base_url = _resolve_env_value(_read_optional_string(endpoints_cfg, "files", f"{row_path}.endpoints"))

        legacy_base_url = _resolve_env_value(_read_optional_string(row, "base_url", row_path))
        legacy_file_base_url = _resolve_env_value(_read_optional_string(row, "upstream_service_base_url", row_path))
        if not chat_base_url and preset is not None:
            chat_base_url = preset.base_url
        if not file_base_url and preset is not None:
            file_base_url = preset.upstream_service_base_url
        chat_base_url = chat_base_url or legacy_base_url
        file_base_url = file_base_url or legacy_file_base_url or chat_base_url

        api_key = _resolve_api_key(
            api_key=_read_optional_string(row, "api_key", row_path),
            api_key_env=_read_optional_string(row, "api_key_env", row_path),
        )
        if api_key is None and preset is not None:
            api_key = preset.api_key

        limits_cfg = _read_optional_object(row, "limits", row_path) or {}
        context_window = _read_optional_int(limits_cfg, "context_window", f"{row_path}.limits")
        if context_window is None:
            context_window = _read_optional_int(row, "context_window", row_path)

        capabilities, default_reasoning_profile = _parse_capabilities(row, row_path)
        native_multimodal_mode = _resolve_native_multimodal_from_profile(
            row=row,
            row_path=row_path,
            provider_name=provider,
            capabilities=capabilities,
        )

        profiles.append(
            ModelProfile(
                id=model_id,
                display_name=display_name or present_model_name(model_id),
                provider_name=provider,
                provider_family=_provider_family(provider),
                upstream_model=upstream_model,
                chat_base_url=chat_base_url,
                file_base_url=file_base_url,
                api_key=api_key,
                context_window=context_window,
                native_multimodal_mode=native_multimodal_mode,
                supports_thinking=capabilities.reasoning_control != "none",
                capabilities=capabilities,
                default_reasoning_profile=default_reasoning_profile,
            )
        )

    return profiles


def _load_model_profiles(*, strict: bool | None = None) -> list[ModelProfile]:
    strict_mode = settings.model_catalog_strict if strict is None else strict
    path = _resolve_catalog_path()
    if not path.exists():
        message = f"Model catalog file does not exist: {path}"
        if strict_mode:
            raise ModelCatalogError(message)
        logger.warning(message)
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        message = f"Failed to parse model catalog JSON at {path}: {exc}"
        if strict_mode:
            raise ModelCatalogError(message) from exc
        logger.warning(message)
        return []

    if not isinstance(payload, dict):
        message = f"Model catalog root must be an object: {path}"
        if strict_mode:
            raise ModelCatalogError(message)
        logger.warning(message)
        return []

    try:
        return _parse_profiles(payload)
    except ModelCatalogError as exc:
        message = f"Invalid model catalog at {path}: {exc}"
        if strict_mode:
            raise ModelCatalogError(message) from exc
        logger.warning(message)
        return []


def list_model_profiles() -> list[ModelProfile]:
    return _load_model_profiles()


def validate_model_catalog() -> list[ModelProfile]:
    return _load_model_profiles(strict=True)


def resolve_model_profile(model_id: str) -> ModelProfile | None:
    normalized = normalize_model_id(model_id)
    for profile in list_model_profiles():
        if profile.id == normalized:
            return profile
    return None


def _effective_reasoning_default(profile: ModelProfile) -> ReasoningProfile:
    if profile.default_reasoning_profile == "provider_default":
        if "auto" in profile.capabilities.reasoning_profiles:
            return "auto"
        for candidate in ("medium", "high", "low", "max", "off"):
            if candidate in profile.capabilities.reasoning_profiles:
                return cast(ReasoningProfile, candidate)
        return "off"
    return profile.default_reasoning_profile


def _normalize_requested_reasoning_profile(profile: ModelProfile, requested: ReasoningProfile) -> ReasoningProfile:
    supported = profile.capabilities.reasoning_profiles
    if requested == "provider_default":
        return _effective_reasoning_default(profile)
    if requested in supported:
        return requested
    if requested == "off":
        return _effective_reasoning_default(profile)
    if requested == "auto":
        return _effective_reasoning_default(profile)
    return _effective_reasoning_default(profile)


def resolve_reasoning_profile(
    model_id: str,
    requested_enabled: bool | None,
    *,
    requested_profile: ReasoningProfile | None = None,
) -> ReasoningProfile:
    profile = resolve_model_profile(model_id)
    if profile is None or profile.capabilities.reasoning_control == "none":
        return "off"
    if requested_profile is not None:
        return _normalize_requested_reasoning_profile(profile, requested_profile)
    if requested_enabled is False:
        if "off" in profile.capabilities.reasoning_profiles:
            return "off"
        return _effective_reasoning_default(profile)
    if requested_enabled is True:
        if profile.default_reasoning_profile not in {"off", "auto", "provider_default"}:
            return profile.default_reasoning_profile
        if "auto" in profile.capabilities.reasoning_profiles:
            return "auto"
        if profile.capabilities.reasoning_control == "budget":
            return "high"
        if profile.capabilities.reasoning_control in {"toggle", "effort", "prompt_tag"}:
            if "medium" in profile.capabilities.reasoning_profiles:
                return "medium"
            if "high" in profile.capabilities.reasoning_profiles:
                return "high"
            if "low" in profile.capabilities.reasoning_profiles:
                return "low"
            if "max" in profile.capabilities.reasoning_profiles:
                return "max"
        return "auto"
    return _effective_reasoning_default(profile)


def resolve_native_multimodal_mode(model_id: str) -> NativeMultimodalMode:
    profile = resolve_model_profile(model_id)
    if profile is None:
        return "false"
    return profile.native_multimodal_mode


def uses_native_multimodal(model_id: str) -> bool:
    return resolve_native_multimodal_mode(model_id) != "false"


def uses_local_native_multimodal(model_id: str) -> bool:
    return resolve_native_multimodal_mode(model_id) == "local"


def uses_codex_native_multimodal(model_id: str) -> bool:
    return resolve_native_multimodal_mode(model_id) == "codex"


def uses_gemini_native_multimodal(model_id: str) -> bool:
    return resolve_native_multimodal_mode(model_id) == "gemini"


def uses_claude_native_multimodal(model_id: str) -> bool:
    return resolve_native_multimodal_mode(model_id) == "claude"


def build_model_options() -> list[dict[str, object]]:
    options: list[dict[str, object]] = []
    for profile in list_model_profiles():
        options.append(
            {
                "id": profile.id,
                "label": profile.display_name,
                "supports_thinking": profile.capabilities.reasoning_control != "none",
                "supports_thinking_trace": profile.capabilities.reasoning_visibility != "none",
                "supports_attachment_upload": profile.capabilities.supports_attachment_upload,
                "provider_name": profile.provider_name,
                "provider_family": profile.provider_family,
                "native_multimodal_mode": profile.native_multimodal_mode,
                "reasoning_control": profile.capabilities.reasoning_control,
                "default_reasoning_profile": _effective_reasoning_default(profile),
                "capabilities": {
                    "input": {
                        "text": profile.capabilities.input_text,
                        "image": profile.capabilities.input_image,
                        "pdf": profile.capabilities.input_pdf,
                        "other_file": profile.capabilities.input_other_file,
                        "audio": profile.capabilities.input_audio,
                    },
                    "transport": {
                        "inline_data": profile.capabilities.transport_inline_data,
                        "file_upload": profile.capabilities.transport_file_upload,
                        "remote_url": profile.capabilities.transport_remote_url,
                    },
                    "reasoning": {
                        "control": profile.capabilities.reasoning_control,
                        "supported_profiles": list(profile.capabilities.reasoning_profiles),
                        "visibility": profile.capabilities.reasoning_visibility,
                        "continuation": profile.capabilities.reasoning_continuation,
                        "visible_trace": profile.capabilities.reasoning_visible_trace,
                        "summary_only": profile.capabilities.reasoning_summary_only,
                    },
                    "tools": {
                        "function_calling": profile.capabilities.tools_function_calling,
                        "parallel_calls": profile.capabilities.tools_parallel_calls,
                        "forced_call": profile.capabilities.tools_forced_call,
                    },
                    "stream": {
                        "text": profile.capabilities.stream_text,
                        "reasoning": profile.capabilities.stream_reasoning,
                        "tool_call": profile.capabilities.stream_tool_call,
                        "usage": profile.capabilities.stream_usage,
                    },
                    "state": {
                        "previous_response": profile.capabilities.state_previous_response,
                    },
                },
                "chat_model": None,
                "reasoning_model": None,
            }
        )
    return options


def normalize_model(model_id: str) -> str:
    return normalize_model_id(model_id)
