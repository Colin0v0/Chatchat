from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Literal, TypedDict, cast

from ..core.config import BASE_DIR, settings
from .capabilities import DiscoveredModel, Provider, model_provider_and_name, normalize_model

logger = logging.getLogger("chatchat.model_catalog")

ThinkingMode = Literal["force_on", "force_off", "default_on", "default_off"]


class ModelCatalogError(RuntimeError):
    pass


class ModelRoute(TypedDict):
    id: str
    display_name: str | None
    provider: Provider
    upstream_model: str
    base_url: str | None
    api_key: str | None
    thinking_mode: ThinkingMode | None
    context_window: int | None
    supports_image_input: bool
    supports_thinking: bool
    supports_document_input: bool  # 新增：原生文档支持


class ProviderPreset(TypedDict):
    provider: Provider | None
    base_url: str | None
    api_key: str | None


def _resolve_catalog_path() -> Path:
    configured = Path(settings.model_catalog_path)
    if configured.is_absolute():
        return configured
    return BASE_DIR / configured


def _normalize_provider(value: str | None, fallback_model_id: str) -> Provider:
    if value in ("ollama", "openai", "openai_local"):
        return cast(Provider, value)
    provider, _ = model_provider_and_name(fallback_model_id)
    return provider


def _normalize_thinking_mode(value: str) -> ThinkingMode:
    normalized = value.strip().lower()
    if normalized in ("force_on", "force_off", "default_on", "default_off"):
        return cast(ThinkingMode, normalized)
    raise ModelCatalogError(
        "Invalid thinking_mode. Expected one of: force_on, force_off, default_on, default_off"
    )


def _resolve_api_key(*, api_key: str | None, api_key_env: str | None) -> str | None:
    direct = (api_key or "").strip()
    if direct:
        return direct
    env_name = (api_key_env or "").strip()
    if not env_name:
        return None
    value = os.getenv(env_name, "").strip()
    return value or None


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

        provider_raw = item.get("provider")
        if provider_raw is not None and not isinstance(provider_raw, str):
            raise ModelCatalogError(f"providers.{name}.provider must be string when provided")
        provider: Provider | None = None
        if isinstance(provider_raw, str) and provider_raw.strip():
            provider = _normalize_provider(provider_raw.strip(), "ollama:placeholder")

        base_url_raw = item.get("base_url")
        if base_url_raw is not None and not isinstance(base_url_raw, str):
            raise ModelCatalogError(f"providers.{name}.base_url must be string when provided")
        base_url = base_url_raw.strip() if isinstance(base_url_raw, str) else ""

        api_key_raw = item.get("api_key")
        if api_key_raw is not None and not isinstance(api_key_raw, str):
            raise ModelCatalogError(f"providers.{name}.api_key must be string when provided")
        api_key_env_raw = item.get("api_key_env")
        if api_key_env_raw is not None and not isinstance(api_key_env_raw, str):
            raise ModelCatalogError(f"providers.{name}.api_key_env must be string when provided")
        api_key = _resolve_api_key(
            api_key=api_key_raw if isinstance(api_key_raw, str) else None,
            api_key_env=api_key_env_raw if isinstance(api_key_env_raw, str) else None,
        )

        presets[name.strip()] = ProviderPreset(
            provider=provider,
            base_url=base_url or None,
            api_key=api_key,
        )

    return presets


def _parse_routes(payload: dict[str, object]) -> list[ModelRoute]:
    presets = _parse_provider_presets(payload)
    rows = payload.get("models")
    if not isinstance(rows, list):
        raise ModelCatalogError("model catalog must contain a 'models' array")

    routes: list[ModelRoute] = []
    seen_model_ids: set[str] = set()

    for index, row in enumerate(rows):
        row_path = f"models[{index}]"
        if not isinstance(row, dict):
            raise ModelCatalogError(f"{row_path} must be an object")

        model_id_raw = row.get("id")
        if not isinstance(model_id_raw, str) or not model_id_raw.strip():
            raise ModelCatalogError(f"{row_path}.id must be a non-empty string")
        model_id = normalize_model(model_id_raw.strip())
        if model_id in seen_model_ids:
            raise ModelCatalogError(f"Duplicate model id in catalog: {model_id}")
        seen_model_ids.add(model_id)

        enabled_raw = row.get("enabled", True)
        if not isinstance(enabled_raw, bool):
            raise ModelCatalogError(f"{row_path}.enabled must be boolean")
        if not enabled_raw:
            continue

        display_name_raw = row.get("display_name")
        if display_name_raw is not None and not isinstance(display_name_raw, str):
            raise ModelCatalogError(f"{row_path}.display_name must be string when provided")
        display_name = display_name_raw.strip() if isinstance(display_name_raw, str) else ""

        provider_ref_raw = row.get("provider_ref")
        if provider_ref_raw is not None and not isinstance(provider_ref_raw, str):
            raise ModelCatalogError(f"{row_path}.provider_ref must be string when provided")
        provider_ref = provider_ref_raw.strip() if isinstance(provider_ref_raw, str) else ""
        preset = None
        if provider_ref:
            preset = presets.get(provider_ref)
            if preset is None:
                raise ModelCatalogError(f"{row_path}.provider_ref references unknown provider preset: {provider_ref}")

        provider_raw = row.get("provider")
        if provider_raw is not None and not isinstance(provider_raw, str):
            raise ModelCatalogError(f"{row_path}.provider must be string when provided")
        provider_source = provider_raw.strip() if isinstance(provider_raw, str) else ""
        if not provider_source and preset is not None and preset.get("provider"):
            provider_source = cast(str, preset["provider"])
        provider = _normalize_provider(provider_source or None, model_id)

        _, model_name = model_provider_and_name(model_id)
        upstream_raw = row.get("upstream_model")
        if upstream_raw is not None and not isinstance(upstream_raw, str):
            raise ModelCatalogError(f"{row_path}.upstream_model must be string when provided")
        upstream_model = upstream_raw.strip() if isinstance(upstream_raw, str) else ""
        if not upstream_model:
            upstream_model = model_name

        base_url_raw = row.get("base_url")
        if base_url_raw is not None and not isinstance(base_url_raw, str):
            raise ModelCatalogError(f"{row_path}.base_url must be string when provided")
        base_url = base_url_raw.strip() if isinstance(base_url_raw, str) else ""
        if not base_url and preset is not None and preset.get("base_url"):
            base_url = cast(str, preset["base_url"])

        api_key_raw = row.get("api_key")
        if api_key_raw is not None and not isinstance(api_key_raw, str):
            raise ModelCatalogError(f"{row_path}.api_key must be string when provided")
        api_key = api_key_raw.strip() if isinstance(api_key_raw, str) else ""

        api_key_env_raw = row.get("api_key_env")
        if api_key_env_raw is not None and not isinstance(api_key_env_raw, str):
            raise ModelCatalogError(f"{row_path}.api_key_env must be string when provided")
        api_key_env = api_key_env_raw.strip() if isinstance(api_key_env_raw, str) else ""
        resolved_api_key = _resolve_api_key(api_key=api_key or None, api_key_env=api_key_env or None)
        if resolved_api_key is None and preset is not None:
            resolved_api_key = preset.get("api_key")

        thinking_mode_raw = row.get("thinking_mode")
        thinking_mode: ThinkingMode | None = None
        if thinking_mode_raw is not None:
            if not isinstance(thinking_mode_raw, str):
                raise ModelCatalogError(f"{row_path}.thinking_mode must be string when provided")
            try:
                thinking_mode = _normalize_thinking_mode(thinking_mode_raw)
            except ModelCatalogError as exc:
                raise ModelCatalogError(f"{row_path}.thinking_mode {exc}") from exc

        context_window_raw = row.get("context_window")
        context_window: int | None = None
        if context_window_raw is not None:
            if isinstance(context_window_raw, bool) or not isinstance(context_window_raw, int) or context_window_raw <= 0:
                raise ModelCatalogError(f"{row_path}.context_window must be a positive integer")
            context_window = context_window_raw

        supports_image_input_raw = row.get("supports_image_input", False)
        if not isinstance(supports_image_input_raw, bool):
            raise ModelCatalogError(f"{row_path}.supports_image_input must be boolean")
        supports_image_input = supports_image_input_raw

        # 新增：读取 supports_document_input 配置
        supports_document_input_raw = row.get("supports_document_input", False)
        if not isinstance(supports_document_input_raw, bool):
            raise ModelCatalogError(f"{row_path}.supports_document_input must be boolean")
        supports_document_input = supports_document_input_raw

        supports_thinking_raw = row.get("supports_thinking")
        if supports_thinking_raw is not None and not isinstance(supports_thinking_raw, bool):
            raise ModelCatalogError(f"{row_path}.supports_thinking must be boolean when provided")

        if isinstance(supports_thinking_raw, bool):
            supports_thinking = supports_thinking_raw
        elif thinking_mode in ("force_on", "default_on"):
            supports_thinking = True
        elif provider in ("ollama", "openai_local"):
            supports_thinking = True
        else:
            supports_thinking = False

        routes.append(
            ModelRoute(
                id=model_id,
                display_name=display_name or None,
                provider=provider,
                upstream_model=upstream_model,
                base_url=base_url or None,
                api_key=resolved_api_key,
                thinking_mode=thinking_mode,
                context_window=context_window,
                supports_image_input=supports_image_input,
                supports_thinking=supports_thinking,
                supports_document_input=supports_document_input,  # 新增
            )
        )

    return routes


def load_model_routes(*, strict: bool | None = None) -> list[ModelRoute]:
    strict_mode = settings.model_catalog_strict if strict is None else strict
    path = _resolve_catalog_path()
    if not path.exists():
        message = f"Model catalog file does not exist: {path}"
        if strict_mode:
            raise ModelCatalogError(message)
        logger.warning("%s; falling back to provider discovery", message)
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        message = f"Failed to parse model catalog JSON at {path}: {exc}"
        if strict_mode:
            raise ModelCatalogError(message) from exc
        logger.warning("%s; falling back to provider discovery", message)
        return []

    if not isinstance(payload, dict):
        message = f"Model catalog root must be an object: {path}"
        if strict_mode:
            raise ModelCatalogError(message)
        logger.warning("%s; falling back to provider discovery", message)
        return []

    try:
        routes = _parse_routes(payload)
    except ModelCatalogError as exc:
        message = f"Invalid model catalog at {path}: {exc}"
        if strict_mode:
            raise ModelCatalogError(message) from exc
        logger.warning("%s; falling back to provider discovery", message)
        return []

    if routes:
        legacy_values = {
            "OPENAI_MODEL_ALLOWLIST": settings.openai_model_allowlist,
            "OPENAI_LOCAL_MODEL_ALLOWLIST": settings.openai_local_model_allowlist,
        }
        active_legacy = [key for key, value in legacy_values.items() if str(value).strip()]
        if active_legacy:
            logger.warning(
                "Model catalog is active; provider allowlists are ignored in strict flow: %s",
                ", ".join(active_legacy),
            )

    return routes


def validate_model_catalog() -> list[ModelRoute]:
    return load_model_routes(strict=True)


def list_catalog_discovered_models() -> list[DiscoveredModel]:
    routes = load_model_routes()
    discovered: list[DiscoveredModel] = []
    for route in routes:
        item: DiscoveredModel = {
            "id": route["id"],
            "supports_image_input": route["supports_image_input"],
            "supports_thinking": route["supports_thinking"],
            "supports_document_input": route["supports_document_input"],
        }
        if route.get("display_name"):
            item["display_name"] = route["display_name"]
        discovered.append(item)
    return discovered


def resolve_model_route(model: str) -> ModelRoute | None:
    normalized = normalize_model(model)
    for route in load_model_routes():
        if route["id"] == normalized:
            return route
    return None


def resolve_effective_thinking(
    model: str,
    requested: bool | None,
    *,
    thinking_mode: ThinkingMode | None = None,
) -> bool | None:
    if thinking_mode == "force_on":
        return True
    if thinking_mode == "force_off":
        return False
    if thinking_mode == "default_on":
        return True if requested is None else requested
    if thinking_mode == "default_off":
        return False if requested is None else requested
    return requested


def resolve_context_window(model: str) -> int | None:
    route = resolve_model_route(model)
    if route is None:
        return None
    return route.get("context_window")
