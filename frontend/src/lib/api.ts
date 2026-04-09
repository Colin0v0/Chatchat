import type {
  AuthSession,
  AudioTranscriptionResult,
  ChatStreamEvent,
  ChatStreamRequest,
  ConversationDetail,
  ConversationSummary,
  MemoryCollection,
  MemoryDocument,
  MemoryItem,
  MemoryLayerCollection,
  MemoryPromotePayload,
  MemoryUpsertPayload,
  ModelOption,
  ModelsPayload,
  RagReindexResult,
  RegenerateChatRequest,
  FeedbackValue,
} from "../types";
import { toModelLabel } from "./models";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";
let unauthorizedHandler: (() => void) | null = null;

export class ApiError extends Error {
  status: number;
  code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

export function toApiUrl(path: string): string {
  if (!path.startsWith("/")) {
    return path;
  }
  return `${API_BASE}${path}`;
}

async function readErrorPayload(response: Response): Promise<{ code: string | null; message: string }> {
  const raw = await response.text();
  if (!raw) {
    return {
      code: null,
      message: `Request failed: ${response.status}`,
    };
  }

  try {
    const parsed = JSON.parse(raw) as {
      code?: unknown;
      detail?: unknown;
      message?: unknown;
    };
    if (parsed.detail && typeof parsed.detail === "object") {
      const detail = parsed.detail as { code?: unknown; message?: unknown };
      if (typeof detail.message === "string" && detail.message.trim()) {
        return {
          code: typeof detail.code === "string" ? detail.code : null,
          message: detail.message,
        };
      }
    }
    if (typeof parsed.detail === "string" && parsed.detail.trim()) {
      return {
        code: typeof parsed.code === "string" ? parsed.code : null,
        message: parsed.detail,
      };
    }
    if (typeof parsed.message === "string" && parsed.message.trim()) {
      return {
        code: typeof parsed.code === "string" ? parsed.code : null,
        message: parsed.message,
      };
    }
  } catch {
    return {
      code: null,
      message: raw,
    };
  }

  return {
    code: null,
    message: raw,
  };
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(toApiUrl(path), {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const { code, message } = await readErrorPayload(response);
    if (response.status === 401) {
      unauthorizedHandler?.();
    }
    throw new ApiError(message, response.status, code);
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
    supports_attachment_upload: true,
    chat_model: null,
    reasoning_model: null,
  };
}

function ensureArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function normalizeMemoryItem(value: unknown): MemoryItem | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const payload = value as Record<string, unknown>;
  const id = typeof payload.id === "number" ? payload.id : null;
  const title = typeof payload.title === "string" ? payload.title : "";
  if (id == null || !title.trim()) {
    return null;
  }

  const scope =
    payload.scope === "global" || payload.scope === "conversation" || payload.scope === "working"
      ? payload.scope
      : "conversation";
  const kind =
    payload.kind === "profile" ||
    payload.kind === "preference" ||
    payload.kind === "goal" ||
    payload.kind === "project" ||
    payload.kind === "fact" ||
    payload.kind === "constraint"
      ? payload.kind
      : "fact";
  const status =
    payload.status === "active" || payload.status === "candidate" || payload.status === "archived"
      ? payload.status
      : "active";
  const tags = ensureArray<unknown>(payload.tags)
    .map((tag) => (typeof tag === "string" ? tag.trim() : ""))
    .filter(Boolean);

  return {
    id,
    scope,
    kind,
    title,
    detail: typeof payload.detail === "string" ? payload.detail : "",
    tags,
    confidence:
      typeof payload.confidence === "number" && Number.isFinite(payload.confidence)
        ? payload.confidence
        : 0.7,
    status,
    source_type: typeof payload.source_type === "string" && payload.source_type.trim() ? payload.source_type : "manual",
    modality: typeof payload.modality === "string" && payload.modality.trim() ? payload.modality : "text",
    write_policy:
      typeof payload.write_policy === "string" && payload.write_policy.trim() ? payload.write_policy : "manual",
    pinned: typeof payload.pinned === "boolean" ? payload.pinned : false,
    active: typeof payload.active === "boolean" ? payload.active : status === "active",
    conversation_id: typeof payload.conversation_id === "number" ? payload.conversation_id : null,
    source_user_message_id: typeof payload.source_user_message_id === "number" ? payload.source_user_message_id : null,
    source_assistant_message_id:
      typeof payload.source_assistant_message_id === "number" ? payload.source_assistant_message_id : null,
    source_attachment_id: typeof payload.source_attachment_id === "number" ? payload.source_attachment_id : null,
    expires_at: typeof payload.expires_at === "string" ? payload.expires_at : null,
    last_confirmed_at: typeof payload.last_confirmed_at === "string" ? payload.last_confirmed_at : null,
    promoted_at: typeof payload.promoted_at === "string" ? payload.promoted_at : null,
    created_at: typeof payload.created_at === "string" ? payload.created_at : null,
    updated_at: typeof payload.updated_at === "string" ? payload.updated_at : null,
    last_used_at: typeof payload.last_used_at === "string" ? payload.last_used_at : null,
  };
}

function normalizeMemoryLayerCollection(value: unknown): MemoryLayerCollection {
  const payload = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  return {
    global_items: ensureArray<unknown>(payload.global_items).map(normalizeMemoryItem).filter((item): item is MemoryItem => item != null),
    conversation_items: ensureArray<unknown>(payload.conversation_items).map(normalizeMemoryItem).filter((item): item is MemoryItem => item != null),
    working_items: ensureArray<unknown>(payload.working_items).map(normalizeMemoryItem).filter((item): item is MemoryItem => item != null),
  };
}

function normalizeMemoryDocuments(value: unknown): MemoryDocument[] {
  return ensureArray<MemoryDocument>(value);
}

function normalizeMemoryCollection(value: unknown): MemoryCollection {
  const payload = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const legacyActiveItems = {
    global_items: payload.global_items,
    conversation_items: payload.conversation_items,
    working_items: payload.working_items,
  };

  return {
    documents: normalizeMemoryDocuments(payload.documents),
    active_items: normalizeMemoryLayerCollection(
      payload.active_items && typeof payload.active_items === "object"
        ? payload.active_items
        : legacyActiveItems,
    ),
    candidate_items: normalizeMemoryLayerCollection(payload.candidate_items),
  };
}

export function fetchConversations() {
  return apiFetch<ConversationSummary[]>("/api/conversations");
}

export function fetchSession() {
  return apiFetch<AuthSession>("/api/auth/session");
}

export async function login(payload: { username: string; password: string }) {
  const response = await fetch(toApiUrl("/api/auth/login"), {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    method: "POST",
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const { code, message } = await readErrorPayload(response);
    throw new ApiError(message, response.status, code);
  }

  return response.json() as Promise<AuthSession>;
}

export async function logout() {
  const response = await fetch(toApiUrl("/api/auth/logout"), {
    credentials: "include",
    method: "POST",
  });
  if (!response.ok) {
    const { code, message } = await readErrorPayload(response);
    throw new ApiError(message, response.status, code);
  }
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
    models: payload.models.map(toModelOption),
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
    credentials: "include",
    method: "DELETE",
  });

  if (!response.ok) {
    const { code, message } = await readErrorPayload(response);
    if (response.status === 401) {
      unauthorizedHandler?.();
    }
    throw new ApiError(message, response.status, code);
  }
}

export function reindexRag() {
  return apiFetch<RagReindexResult>("/api/rag/reindex", {
    method: "POST",
  });
}

export async function fetchMemories(conversationId?: number | null) {
  const suffix =
    conversationId == null ? "" : `?conversation_id=${encodeURIComponent(String(conversationId))}`;
  const payload = await apiFetch<unknown>(`/api/memories${suffix}`);
  return normalizeMemoryCollection(payload);
}

export function createMemory(payload: MemoryUpsertPayload) {
  return apiFetch<MemoryItem>("/api/memories/items", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateMemory(memoryId: number, payload: MemoryUpsertPayload) {
  return apiFetch<MemoryItem>(`/api/memories/items/${memoryId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function promoteMemory(memoryId: number, payload: MemoryPromotePayload) {
  return apiFetch<MemoryItem>(`/api/memories/${memoryId}/promote`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function dismissMemory(memoryId: number) {
  return apiFetch<MemoryItem>(`/api/memories/${memoryId}/dismiss`, {
    method: "POST",
  });
}

export async function deleteMemory(memoryId: number) {
  const response = await fetch(toApiUrl(`/api/memories/items/${memoryId}`), {
    credentials: "include",
    method: "DELETE",
  });

  if (!response.ok) {
    const { code, message } = await readErrorPayload(response);
    if (response.status === 401) {
      unauthorizedHandler?.();
    }
    throw new ApiError(message, response.status, code);
  }
}

interface StreamRequestOptions {
  onEvent: (event: ChatStreamEvent) => void;
  signal?: AbortSignal;
}

function parseNdjsonEvent(raw: string): ChatStreamEvent | null {
  const trimmed = raw.trim();
  if (!trimmed) {
    return null;
  }

  try {
    return JSON.parse(trimmed) as ChatStreamEvent;
  } catch (err) {
    console.warn("[ndjson parse error]", trimmed.substring(0, 100), err);
    return null;
  }
}

async function consumeNdjsonStream(response: Response, onEvent: (event: ChatStreamEvent) => void) {
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
      const event = parseNdjsonEvent(line);
      if (event) {
        onEvent(event);
      }
    }
  }

  buffer += decoder.decode();
  const tailEvent = parseNdjsonEvent(buffer);
  if (tailEvent) {
    onEvent(tailEvent);
  }
}

function audioExtensionForMimeType(mimeType: string): string {
  switch (mimeType) {
    case "audio/mp4":
      return ".mp4";
    case "audio/wav":
    case "audio/wave":
    case "audio/x-wav":
      return ".wav";
    default:
      return ".webm";
  }
}

function appendAudioFile(formData: FormData, file: Blob) {
  const mimeType = file.type || "audio/webm";
  const namedFile =
    file instanceof File
      ? file
      : new File([file], `recording${audioExtensionForMimeType(mimeType)}`, {
          type: mimeType,
          lastModified: Date.now(),
        });
  formData.append("file", namedFile);
}

export async function transcribeAudio(file: Blob): Promise<AudioTranscriptionResult> {
  const formData = new FormData();
  appendAudioFile(formData, file);

  const response = await fetch(toApiUrl("/api/audio/transcribe"), {
    credentials: "include",
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const { code, message } = await readErrorPayload(response);
    if (response.status === 401) {
      unauthorizedHandler?.();
    }
    throw new ApiError(message, response.status, code);
  }
  return response.json() as Promise<AudioTranscriptionResult>;
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
  if (payload.thinking_enabled != null) {
    formData.append("thinking_enabled", String(payload.thinking_enabled));
  }
  payload.files?.forEach((file) => formData.append("files", file));

  const response = await fetch(toApiUrl("/api/chat/stream"), {
    credentials: "include",
    method: "POST",
    body: formData,
    signal: options.signal,
  });

  if (!response.ok) {
    const { code, message } = await readErrorPayload(response);
    if (response.status === 401) {
      unauthorizedHandler?.();
    }
    throw new ApiError(message, response.status, code);
  }

  await consumeNdjsonStream(response, options.onEvent);
}

export async function regenerateChat(payload: RegenerateChatRequest, options: StreamRequestOptions) {
  const response = await fetch(toApiUrl("/api/chat/regenerate"), {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  });

  if (!response.ok) {
    const { code, message } = await readErrorPayload(response);
    if (response.status === 401) {
      unauthorizedHandler?.();
    }
    throw new ApiError(message, response.status, code);
  }

  await consumeNdjsonStream(response, options.onEvent);
}

export function updateMessageFeedback(messageId: number, value: FeedbackValue | null) {
  return apiFetch<{ id: number; feedback: FeedbackValue | null }>(`/api/chat/messages/${messageId}/feedback`, {
    method: "PATCH",
    body: JSON.stringify({ value }),
  });
}
