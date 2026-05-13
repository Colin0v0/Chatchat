import type { ChatStreamEvent, ChatStreamRequest, RegenerateChatRequest } from "../../../types";
import { assertApiResponse, toApiUrl } from "../../../shared/api/http";
import { consumeNdjsonStream } from "../../../shared/api/ndjson";

export interface ChatStreamRequestOptions {
  onEvent: (event: ChatStreamEvent) => void;
  signal?: AbortSignal;
  batchWindowMs?: number;
  runId?: string | null;
  afterSeq?: number | null;
}

export async function streamChat(payload: ChatStreamRequest, options: ChatStreamRequestOptions) {
  const formData = new FormData();
  if (payload.conversation_id) {
    formData.append("conversation_id", String(payload.conversation_id));
  }
  formData.append("message", payload.message);
  if (payload.model) {
    formData.append("model", payload.model);
  }
  if (typeof payload.temperature === "number") {
    formData.append("temperature", String(payload.temperature));
  }
  formData.append("tool_mode", payload.tool_mode);
  payload.knowledge_folders?.forEach((folder) => formData.append("knowledge_folders", folder));
  if (payload.reasoning_profile) {
    formData.append("reasoning_profile", payload.reasoning_profile);
  }
  if (payload.temporary_chat) {
    formData.append("temporary_chat", "true");
  }
  payload.files?.forEach((file) => formData.append("files", file));

  const response = await fetch(toApiUrl("/api/chat/stream"), {
    credentials: "include",
    method: "POST",
    body: formData,
    signal: options.signal,
  });
  await assertApiResponse(response);

  await consumeNdjsonStream<ChatStreamEvent>(response, options.onEvent, options.batchWindowMs);
}

export async function regenerateChat(payload: RegenerateChatRequest, options: ChatStreamRequestOptions) {
  const response = await fetch(toApiUrl("/api/chat/regenerate"), {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  await assertApiResponse(response);

  await consumeNdjsonStream<ChatStreamEvent>(response, options.onEvent, options.batchWindowMs);
}

export async function streamActiveChat(
  conversationId: number,
  options: ChatStreamRequestOptions,
) {
  const params = new URLSearchParams({
    conversation_id: String(conversationId),
  });
  if (options.runId) {
    params.set("run_id", options.runId);
  }
  if (typeof options.afterSeq === "number" && Number.isFinite(options.afterSeq) && options.afterSeq >= 0) {
    params.set("after_seq", String(options.afterSeq));
  }
  const response = await fetch(toApiUrl(`/api/chat/stream/active?${params.toString()}`), {
    credentials: "include",
    method: "GET",
    signal: options.signal,
  });
  await assertApiResponse(response);

  await consumeNdjsonStream<ChatStreamEvent>(response, options.onEvent, options.batchWindowMs);
}

export async function cancelActiveChat(conversationId: number): Promise<void> {
  const response = await fetch(toApiUrl("/api/chat/stream/cancel"), {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ conversation_id: conversationId }),
  });
  await assertApiResponse(response);
}
