const PROVIDER_MODEL_PATTERN = /^(ollama|openai):(.+)$/;

export function toModelLabel(modelId: string): string {
  const matched = modelId.match(PROVIDER_MODEL_PATTERN);
  if (!matched) {
    return modelId;
  }
  return matched[2];
}
