import type {
  ChatStreamEvent,
  ChatStreamRequest,
  ConversationDetail,
  ConversationSummary,
  ModelOption,
  ModelsPayload,
  RagReindexResult,
  RegenerateChatRequest,
} from "../types";
import { toModelLabel } from "./models";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export function toApiUrl(path: string): string {
  if (!path.startsWith("/")) {
    return path;
  }
  return `${API_BASE}${path}`;
}

async function readErrorMessage(response: Response): Promise<string> {
  const raw = await response.text();
  if (!raw) {
    return `Request failed: ${response.status}`;
  }

  try {
    const parsed = JSON.parse(raw) as { detail?: unknown; message?: unknown };
    if (typeof parsed.detail === "string" && parsed.detail.trim()) {
      return parsed.detail;
    }
    if (typeof parsed.message === "string" && parsed.message.trim()) {
      return parsed.message;
    }
  } catch {
    return raw;
  }

  return raw;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(toApiUrl(path), {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  return response.json() as Promise<T>;
}

function toModelOption(model: string | ModelOption): ModelOption {
  if (typeof model !== "string") {
    return model;
  }

  return {
    id: model,
    label: toModelLabel(model),
    supports_thinking: false,
    supports_thinking_trace: false,
    supports_image_input: false,
    supports_attachment_upload: true,
    chat_model: null,
    reasoning_model: null,
  };
}

function normalizeModelOptions(models: Array<string | ModelOption>): ModelOption[] {
  const options = models.map(toModelOption);
  const optionIds = new Set(options.map((item) => item.id));
  const deepseekChat = "openai:deepseek-chat";
  const deepseekReasoner = "openai:deepseek-reasoner";

  if (!optionIds.has(deepseekChat) || !optionIds.has(deepseekReasoner)) {
    return options;
  }

  return options.map((item) => {
    if (item.id !== deepseekChat && item.id !== deepseekReasoner) {
      return item;
    }

    return {
      ...item,
      supports_thinking: true,
      supports_thinking_trace: item.id === deepseekReasoner,
      chat_model: deepseekChat,
      reasoning_model: deepseekReasoner,
    };
  });
}

export function fetchConversations() {
  return apiFetch<ConversationSummary[]>("/api/conversations");
}

export function fetchConversation(conversationId: number) {
  return apiFetch<ConversationDetail>(`/api/conversations/${conversationId}`);
}

export async function fetchModels() {
  const payload = await apiFetch<{
    models: Array<string | ModelOption>;
    default_model: string;
  }>("/api/models");

  return {
    ...payload,
    models: normalizeModelOptions(payload.models),
  } satisfies ModelsPayload;
}

export function renameConversation(conversationId: number, title: string) {
  return apiFetch<ConversationSummary>(`/api/conversations/${conversationId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export async function deleteConversation(conversationId: number) {
  const response = await fetch(toApiUrl(`/api/conversations/${conversationId}`), {
    method: "DELETE",
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }
}

export function reindexRag() {
  return apiFetch<RagReindexResult>("/api/rag/reindex", {
    method: "POST",
  });
}

interface StreamRequestOptions {
  onEvent: (event: ChatStreamEvent) => void;
  signal?: AbortSignal;
}

export async function streamChat(payload: ChatStreamRequest, options: StreamRequestOptions) {
  const formData = new FormData();
  if (payload.conversation_id) {
    formData.append("conversation_id", String(payload.conversation_id));
  }
  formData.append("message", payload.message);
  if (payload.model) {
    formData.append("model", payload.model);
  }
  formData.append("retrieval_mode", payload.retrieval_mode);
  payload.files?.forEach((file) => formData.append("files", file));

  const response = await fetch(toApiUrl("/api/chat/stream"), {
    method: "POST",
    body: formData,
    signal: options.signal,
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  if (!response.body) {
    throw new Error("Streaming is not supported by this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        continue;
      }
      options.onEvent(JSON.parse(trimmed) as ChatStreamEvent);
    }
  }

  if (buffer.trim()) {
    options.onEvent(JSON.parse(buffer) as ChatStreamEvent);
  }
}

export async function regenerateChat(payload: RegenerateChatRequest, options: StreamRequestOptions) {
  const response = await fetch(toApiUrl("/api/chat/regenerate"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  if (!response.body) {
    throw new Error("Streaming is not supported by this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        continue;
      }
      options.onEvent(JSON.parse(trimmed) as ChatStreamEvent);
    }
  }

  if (buffer.trim()) {
    options.onEvent(JSON.parse(buffer) as ChatStreamEvent);
  }
}
