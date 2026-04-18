import type { ModelOption, ReasoningControl, ReasoningProfileValue } from "../types";

export interface ReasoningProfileOption {
  value: ReasoningProfileValue;
  label: string;
}

function fallbackReasoningControl(model: ModelOption): ReasoningControl {
  return model.supports_thinking ? "effort" : "none";
}

export function resolveModelReasoningControl(model: ModelOption): ReasoningControl {
  return model.capabilities?.reasoning.control ?? model.reasoning_control ?? fallbackReasoningControl(model);
}

export function supportedReasoningProfilesForModel(model: ModelOption): ReasoningProfileValue[] {
  const explicit = model.capabilities?.reasoning.supported_profiles;
  if (explicit && explicit.length > 0) {
    return explicit;
  }

  const control = resolveModelReasoningControl(model);
  if (control === "none") {
    return ["off"];
  }
  if (control === "toggle" || control === "prompt_tag") {
    return ["auto", "off", "medium"];
  }
  return ["auto", "off", "low", "medium", "high", "max"];
}

export function resolveModelDefaultReasoningProfile(model: ModelOption): ReasoningProfileValue {
  const resolved = model.default_reasoning_profile ?? "off";
  return resolved === "provider_default" ? "auto" : resolved;
}

export function supportsReasoningSelection(model: ModelOption): boolean {
  return resolveModelReasoningControl(model) !== "none";
}

export function normalizeReasoningProfileForModel(
  model: ModelOption,
  value: ReasoningProfileValue | null | undefined,
): ReasoningProfileValue {
  const control = resolveModelReasoningControl(model);
  const defaultValue = resolveModelDefaultReasoningProfile(model);
  const supportedProfiles = supportedReasoningProfilesForModel(model);
  const normalized = (value ?? defaultValue) === "provider_default" ? "auto" : (value ?? defaultValue);

  if (control === "none") {
    return "off";
  }
  if (supportedProfiles.includes(normalized)) {
    return normalized;
  }
  return defaultValue;
}

function resolvedProfileLabel(value: ReasoningProfileValue): string {
  if (value === "off") {
    return "Off";
  }
  if (value === "low") {
    return "Low";
  }
  if (value === "medium") {
    return "Medium";
  }
  if (value === "high") {
    return "High";
  }
  if (value === "max") {
    return "Max";
  }
  return "Auto";
}

export function reasoningProfileLabelForModel(
  model: ModelOption,
  value: ReasoningProfileValue | null | undefined,
): string {
  const control = resolveModelReasoningControl(model);
  const normalized = normalizeReasoningProfileForModel(model, value);

  if (normalized === "auto") {
    return "Default";
  }
  if (normalized === "off") {
    return "Off";
  }
  if (control === "toggle" || control === "prompt_tag") {
    return "On";
  }
  return resolvedProfileLabel(normalized);
}

export function reasoningProfileOptionsForModel(model: ModelOption): ReasoningProfileOption[] {
  const control = resolveModelReasoningControl(model);
  const defaultProfile = resolveModelDefaultReasoningProfile(model);
  const defaultLabel = reasoningProfileLabelForModel(model, defaultProfile);
  const supportedProfiles = supportedReasoningProfilesForModel(model);
  if (control === "none") {
    return [];
  }

  const options: ReasoningProfileOption[] = [];
  if (supportedProfiles.includes("auto")) {
    options.push({
      value: "auto",
      label: defaultLabel === "Default" ? "Default" : `Default (${defaultLabel})`,
    });
  }
  if (supportedProfiles.includes("off")) {
    options.push({ value: "off", label: "Off" });
  }
  if (control === "toggle" || control === "prompt_tag") {
    if (supportedProfiles.includes("medium")) {
      options.push({ value: "medium", label: "On" });
    }
    return options;
  }
  if (supportedProfiles.includes("low")) {
    options.push({ value: "low", label: "Low" });
  }
  if (supportedProfiles.includes("medium")) {
    options.push({ value: "medium", label: "Medium" });
  }
  if (supportedProfiles.includes("high")) {
    options.push({ value: "high", label: "High" });
  }
  if (supportedProfiles.includes("max")) {
    options.push({ value: "max", label: "Max" });
  }
  return options;
}

export function reasoningRequestValueForModel(
  model: ModelOption,
  value: ReasoningProfileValue | null | undefined,
): ReasoningProfileValue | null {
  if (!supportsReasoningSelection(model)) {
    return null;
  }
  return normalizeReasoningProfileForModel(model, value);
}
