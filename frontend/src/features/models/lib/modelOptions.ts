import { toModelLabel } from "../../../lib/models";
import type { ModelOption } from "../../../types";

export function createModelOption(id: string): ModelOption {
  return {
    id,
    label: toModelLabel(id),
    supports_thinking: false,
    supports_thinking_trace: false,
    supports_attachment_upload: true,
    native_multimodal_mode: "false",
    reasoning_control: "none",
    default_reasoning_profile: "off",
    chat_model: null,
    reasoning_model: null,
  };
}

export function findModelOption(models: ModelOption[], modelId: string): ModelOption {
  return models.find((item) => item.id === modelId) ?? createModelOption(modelId);
}

export function ensureSelectedModel(
  models: ModelOption[],
  modelId: string,
  options: { allowUnknown?: boolean } = {},
): ModelOption[] {
  if (!modelId || models.some((item) => item.id === modelId)) {
    return models;
  }
  if (options.allowUnknown === false) {
    return models;
  }

  return [...models, createModelOption(modelId)];
}

export function resolveInitialSelectedModel(models: ModelOption[], preferredModel: string): string {
  const exactMatch = models.find((item) => item.id === preferredModel);
  return exactMatch?.id ?? models[0]?.id ?? "";
}
