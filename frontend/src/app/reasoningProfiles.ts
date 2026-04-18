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
  const normalized = (value ?? defaultValue) === "provider_default" ? "auto" : (value ?? defaultValue);

  if (control === "none") {
    return "off";
  }
  if (normalized === "off" || normalized === "auto") {
    return normalized;
  }
  if (control === "toggle" || control === "prompt_tag") {
    return "medium";
  }
  if (normalized === "low" || normalized === "medium" || normalized === "high" || normalized === "max") {
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
  if (control === "none") {
    return [];
  }

  const options: ReasoningProfileOption[] = [
    {
      value: "auto",
      label: `Default (${reasoningProfileLabelForModel(model, defaultProfile)})`,
    },
    { value: "off", label: "Off" },
  ];

  if (control === "toggle" || control === "prompt_tag") {
    options.push({ value: "medium", label: "On" });
    return options;
  }

  options.push(
    { value: "low", label: "Low" },
    { value: "medium", label: "Medium" },
    { value: "high", label: "High" },
    { value: "max", label: "Max" },
  );
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
