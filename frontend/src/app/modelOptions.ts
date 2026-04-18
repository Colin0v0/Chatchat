import { toModelLabel } from "../lib/models";
import type { ModelOption } from "../types";
import { INITIAL_CHAT_MODEL, INITIAL_REASONING_MODEL } from "./constants";

export function createModelOption(id: string): ModelOption {
  if (id === INITIAL_CHAT_MODEL) {
    return {
      id,
      label: "deepseek-chat",
      supports_thinking: false,
      supports_thinking_trace: false,
      supports_attachment_upload: true,
      reasoning_control: "none",
      default_reasoning_profile: "off",
      chat_model: null,
      reasoning_model: null,
    };
  }

  if (id === INITIAL_REASONING_MODEL) {
    return {
      id,
      label: "deepseek-reasoner",
      supports_thinking: true,
      supports_thinking_trace: true,
      supports_attachment_upload: true,
      reasoning_control: "effort",
      default_reasoning_profile: "medium",
      chat_model: null,
      reasoning_model: null,
    };
  }

  return {
    id,
    label: toModelLabel(id),
    supports_thinking: false,
    supports_thinking_trace: false,
    supports_attachment_upload: true,
    reasoning_control: "none",
    default_reasoning_profile: "off",
    chat_model: null,
    reasoning_model: null,
  };
}

export function createInitialModelOptions(): ModelOption[] {
  return [createModelOption(INITIAL_CHAT_MODEL), createModelOption(INITIAL_REASONING_MODEL)];
}

export function findModelOption(models: ModelOption[], modelId: string): ModelOption {
  return models.find((item) => item.id === modelId) ?? createModelOption(modelId);
}

export function ensureSelectedModel(models: ModelOption[], modelId: string): ModelOption[] {
  if (!modelId || models.some((item) => item.id === modelId)) {
    return models;
  }

  return [...models, createModelOption(modelId)];
}

export function resolveInitialSelectedModel(models: ModelOption[], preferredModel: string): string {
  return findModelOption(models, preferredModel).id;
}
