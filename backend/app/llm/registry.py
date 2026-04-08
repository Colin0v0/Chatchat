from __future__ import annotations

from .capabilities import DiscoveredModel, ModelOption, present_model_name


def build_model_options(models: list[DiscoveredModel]) -> list[ModelOption]:
    unique_models = list(dict.fromkeys(item["id"] for item in models))
    discovered_by_id = {item["id"]: item for item in models}

    options: list[ModelOption] = []
    for model in unique_models:
        display_name = discovered_by_id.get(model, {}).get("display_name", "")
        supports_native_thinking = discovered_by_id.get(model, {}).get("supports_thinking", False)
        options.append(
            ModelOption(
                id=model,
                label=display_name or present_model_name(model),
                supports_thinking=supports_native_thinking,
                supports_thinking_trace=supports_native_thinking,
                supports_attachment_upload=True,
                chat_model=None,
                reasoning_model=None,
            )
        )

    return options
