import { toModelLabel } from "../lib/models";
import type { ModelOption } from "../types";
import { INITIAL_CHAT_MODEL, INITIAL_REASONING_MODEL } from "./constants";

export function createModelOption(id: string): ModelOption {
  if (id === INITIAL_CHAT_MODEL) {
    return {
      id,
      label: "deepseek-chat",
      supports_thinking: false,
      supports_thinking_trace: true,
      supports_attachment_upload: true,
      native_multimodal_mode: "false",
      reasoning_control: "none",
      default_reasoning_profile: "off",
      capabilities: {
        input: {
          text: true,
          image: true,
          pdf: true,
          other_file: true,
          audio: true,
        },
        transport: {
          inline_data: false,
          file_upload: false,
          remote_url: true,
        },
        reasoning: {
          control: "none",
          supported_profiles: ["off"],
          visibility: "summary",
          continuation: "signature",
          visible_trace: true,
          summary_only: true,
        },
        tools: {
          function_calling: true,
          parallel_calls: true,
          forced_call: true,
        },
        stream: {
          text: true,
          reasoning: false,
          tool_call: true,
          usage: true,
        },
        state: {
          previous_response: true,
        },
      },
      chat_model: null,
      reasoning_model: null,
    };
  }

  if (id === INITIAL_REASONING_MODEL) {
    return {
      id,
      label: "deepseek-reasoner",
      supports_thinking: false,
      supports_thinking_trace: true,
      supports_attachment_upload: true,
      native_multimodal_mode: "false",
      reasoning_control: "none",
      default_reasoning_profile: "off",
      capabilities: {
        input: {
          text: true,
          image: true,
          pdf: true,
          other_file: true,
          audio: false,
        },
        transport: {
          inline_data: false,
          file_upload: false,
          remote_url: true,
        },
        reasoning: {
          control: "none",
          supported_profiles: ["off"],
          visibility: "full",
          continuation: "stateful",
          visible_trace: true,
          summary_only: false,
        },
        tools: {
          function_calling: true,
          parallel_calls: true,
          forced_call: false,
        },
        stream: {
          text: true,
          reasoning: true,
          tool_call: false,
          usage: false,
        },
        state: {
          previous_response: false,
        },
      },
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
    native_multimodal_mode: "false",
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
