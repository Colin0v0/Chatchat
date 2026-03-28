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
  const response = await fetch(`${API_BASE}${path}`, {
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
  const response = await fetch(`${API_BASE}/api/conversations/${conversationId}`, {
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

export async function streamChat(
  payload: ChatStreamRequest,
  handlers: {
    onEvent: (event: ChatStreamEvent) => void;
    signal?: AbortSignal;
  },
) {
  const response = await fetch(`${API_BASE}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: handlers.signal,
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  if (!response.body) {
    throw new Error("Streaming response is not available");
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
    const parts = buffer.split("\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      if (!part.trim()) {
        continue;
      }
      handlers.onEvent(JSON.parse(part) as ChatStreamEvent);
    }
  }

  const rest = buffer.trim();
  if (rest) {
    handlers.onEvent(JSON.parse(rest) as ChatStreamEvent);
  }
}

export async function regenerateChat(
  payload: RegenerateChatRequest,
  handlers: {
    onEvent: (event: ChatStreamEvent) => void;
    signal?: AbortSignal;
  },
) {
  const response = await fetch(`${API_BASE}/api/chat/regenerate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: handlers.signal,
  });

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  if (!response.body) {
    throw new Error("Streaming response is not available");
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
    const parts = buffer.split("\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      if (!part.trim()) {
        continue;
      }
      handlers.onEvent(JSON.parse(part) as ChatStreamEvent);
    }
  }

  const rest = buffer.trim();
  if (rest) {
    handlers.onEvent(JSON.parse(rest) as ChatStreamEvent);
  }
}
