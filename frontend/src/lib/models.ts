export function toModelLabel(modelId: string): string {
  const separatorIndex = modelId.indexOf(":");
  if (separatorIndex < 0 || separatorIndex === modelId.length - 1) {
    return modelId;
  }
  return modelId.slice(separatorIndex + 1);
}
