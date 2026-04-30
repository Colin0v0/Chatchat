import { isRecord } from "../../../shared/lib/browserCache";
import type { ModelOption, ModelsPayload } from "../../../types";

export function isModelOption(value: unknown): value is ModelOption {
  return (
    isRecord(value)
    && typeof value.id === "string"
    && typeof value.label === "string"
    && typeof value.supports_thinking === "boolean"
    && typeof value.supports_thinking_trace === "boolean"
    && typeof value.supports_attachment_upload === "boolean"
    && (typeof value.chat_model === "string" || value.chat_model === null)
    && (typeof value.reasoning_model === "string" || value.reasoning_model === null)
  );
}

export function isModelsPayload(value: unknown): value is ModelsPayload {
  return (
    isRecord(value)
    && Array.isArray(value.models)
    && value.models.every(isModelOption)
    && typeof value.default_model === "string"
  );
}
