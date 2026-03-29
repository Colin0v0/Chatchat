from __future__ import annotations

from .capabilities import DiscoveredModel, ModelOption, namespaced_model, present_model_name


def build_model_options(models: list[DiscoveredModel]) -> list[ModelOption]:
    unique_models = list(dict.fromkeys(item["id"] for item in models))
    discovered_by_id = {item["id"]: item for item in models}
    available = set(unique_models)

    deepseek_chat = namespaced_model("openai", "deepseek-chat")
    deepseek_reasoner = namespaced_model("openai", "deepseek-reasoner")
    reasoning_pairs: dict[str, tuple[str, str]] = {}
    reasoning_trace_models: set[str] = set()

    if deepseek_chat in available and deepseek_reasoner in available:
        reasoning_pairs[deepseek_chat] = (deepseek_chat, deepseek_reasoner)
        reasoning_pairs[deepseek_reasoner] = (deepseek_chat, deepseek_reasoner)
        reasoning_trace_models.add(deepseek_reasoner)

    options: list[ModelOption] = []
    for model in unique_models:
        pair = reasoning_pairs.get(model)
        chat_model = pair[0] if pair else None
        reasoning_model = pair[1] if pair else None
        supports_image_input = discovered_by_id.get(model, {}).get("supports_image_input", False)
        options.append(
            ModelOption(
                id=model,
                label=present_model_name(model),
                supports_thinking=pair is not None,
                supports_thinking_trace=model in reasoning_trace_models,
                supports_image_input=supports_image_input,
                supports_attachment_upload=True,
                chat_model=chat_model,
                reasoning_model=reasoning_model,
            )
        )

    return options
