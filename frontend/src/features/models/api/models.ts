import type { ModelOption, ModelsPayload } from "../../../types";
import { apiFetch } from "../../../shared/api/http";
import { toModelLabel } from "../../../lib/models";

function toModelOption(model: string | ModelOption): ModelOption {
  if (typeof model !== "string") {
    return model;
  }

  return {
    id: model,
    label: toModelLabel(model),
    supports_thinking: false,
    supports_thinking_trace: false,
    supports_attachment_upload: true,
    native_multimodal_mode: "false",
    chat_model: null,
    reasoning_model: null,
  };
}

export async function fetchModels() {
  const payload = await apiFetch<{
    models: Array<string | ModelOption>;
    default_model: string;
  }>("/api/models");

  return {
    ...payload,
    models: payload.models.map(toModelOption),
  } satisfies ModelsPayload;
}
