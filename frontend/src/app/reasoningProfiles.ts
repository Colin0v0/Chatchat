import type { ModelOption, ReasoningControl, ReasoningProfileValue } from "../types";

export interface ReasoningProfileOption {
  value: ReasoningProfileValue;
  label: string;
}

const CONCRETE_REASONING_PROFILE_ORDER: ReasoningProfileValue[] = ["medium", "low", "high", "max", "off"];

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

function concreteReasoningProfilesForModel(model: ModelOption): ReasoningProfileValue[] {
  return supportedReasoningProfilesForModel(model).filter(
    (profile): profile is Exclude<ReasoningProfileValue, "auto" | "provider_default"> =>
      profile !== "auto" && profile !== "provider_default",
  );
}

function fallbackConcreteReasoningProfile(model: ModelOption): ReasoningProfileValue {
  const concreteProfiles = concreteReasoningProfilesForModel(model);

  for (const candidate of CONCRETE_REASONING_PROFILE_ORDER) {
    if (concreteProfiles.includes(candidate)) {
      return candidate;
    }
  }

  return "off";
}

export function resolveModelDefaultReasoningProfile(model: ModelOption): ReasoningProfileValue {
  const resolved = model.default_reasoning_profile ?? "off";
  if (resolved === "provider_default" || resolved === "auto") {
    return fallbackConcreteReasoningProfile(model);
  }

  if (concreteReasoningProfilesForModel(model).includes(resolved)) {
    return resolved;
  }

  return fallbackConcreteReasoningProfile(model);
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
  const concreteProfiles = concreteReasoningProfilesForModel(model);
  const candidate = value ?? defaultValue;
  const normalized =
    candidate === "provider_default" || candidate === "auto" ? defaultValue : candidate;

  if (control === "none") {
    return "off";
  }
  if (concreteProfiles.includes(normalized)) {
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
  return "Medium";
}

export function reasoningProfileLabelForModel(
  model: ModelOption,
  value: ReasoningProfileValue | null | undefined,
): string {
  const normalized = normalizeReasoningProfileForModel(model, value);
  return resolvedProfileLabel(normalized);
}

export function reasoningProfileOptionsForModel(model: ModelOption): ReasoningProfileOption[] {
  const control = resolveModelReasoningControl(model);
  const supportedProfiles = concreteReasoningProfilesForModel(model);
  if (control === "none") {
    return [];
  }

  const options: ReasoningProfileOption[] = [];
  if (supportedProfiles.includes("off")) {
    options.push({ value: "off", label: "Off" });
  }
  if (control === "toggle" || control === "prompt_tag") {
    if (supportedProfiles.includes("medium")) {
      options.push({ value: "medium", label: "Medium" });
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
