import type { ModelOption } from "../types";

function hasCapabilityData(model: ModelOption): boolean {
  return Boolean(model.capabilities);
}

function normalizeModelBrandSource(model: ModelOption): string {
  return [model.id, model.label, model.chat_model, model.reasoning_model, model.provider_name, model.provider_family]
    .filter((value): value is string => typeof value === "string" && value.length > 0)
    .join(" ")
    .toLowerCase();
}

function isDeepSeekModel(model: ModelOption): boolean {
  return normalizeModelBrandSource(model).includes("deepseek");
}

export function reasoningDisplayLabel(model: ModelOption): string | null {
  const reasoning = model.capabilities?.reasoning;
  if (reasoning) {
    if (reasoning.visibility === "full") {
      return "思考过程";
    }
    if (reasoning.visibility === "summary") {
      return "思考摘要";
    }
    if (model.supports_thinking) {
      return "隐式推理";
    }
    return null;
  }

  if (!model.supports_thinking) {
    return null;
  }
  return model.supports_thinking_trace ? "思考过程" : "隐式推理";
}

export function nativeMultimodalLabel(model: ModelOption): string | null {
  if (!model.supports_attachment_upload) {
    return null;
  }

  switch (model.native_multimodal_mode) {
    case "codex":
      return "原生图文文件";
    case "gemini":
      return "原生图像文档";
    case "claude":
      return "原生图像/PDF";
    case "local":
      return "原生文件引用";
    default:
      return hasCapabilityData(model) ? "附件上下文" : "附件支持";
  }
}

export function providerBadgeLabel(model: ModelOption): string | null {
  if (isDeepSeekModel(model)) {
    return "DeepSeek";
  }

  const provider = model.provider_name?.trim();
  if (!provider) {
    return null;
  }
  if (provider === "codex") {
    return "OpenAI";
  }
  if (provider === "claude") {
    return "Anthropic";
  }
  if (provider === "gemini") {
    return "Google";
  }
  if (provider === "openai_local") {
    return "OpenAI Relay";
  }
  if (provider === "trio") {
    return "Trio Relay";
  }
  if (provider === "openai") {
    return "OpenAI兼容";
  }
  return provider;
}

export function thinkingPanelLabels(model: ModelOption | null | undefined): {
  streamingLabel: string;
  settledLabel: string;
} {
  const reasoning = model?.capabilities?.reasoning;
  if (reasoning?.visibility === "summary") {
    return {
      streamingLabel: "思考中",
      settledLabel: "思考摘要",
    };
  }

  if (reasoning?.visibility === "full" || model?.supports_thinking_trace) {
    return {
      streamingLabel: "思考中",
      settledLabel: "思考过程",
    };
  }

  return {
    streamingLabel: "思考中",
    settledLabel: "推理结果",
  };
}
