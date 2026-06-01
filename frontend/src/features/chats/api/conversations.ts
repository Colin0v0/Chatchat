import type {
  ConversationDetail,
  ConversationMessagePage,
  ConversationSummary,
  FeedbackValue,
  MemoryCandidateUpdatePayload,
  MemoryItem,
} from "../../../types";
import { apiFetch, assertApiResponse, toApiUrl } from "../../../shared/api/http";

export function fetchConversations(projectId?: number | null) {
  const params = new URLSearchParams();
  if (projectId) {
    params.set("project_id", String(projectId));
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return apiFetch<ConversationSummary[]>(`/api/conversations${suffix}`);
}

export function fetchConversation(
  conversationId: number,
  options?: {
    limit?: number;
    signal?: AbortSignal;
  },
) {
  const params = new URLSearchParams();
  if (options?.limit != null) {
    params.set("message_limit", String(options.limit));
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return apiFetch<ConversationDetail>(`/api/conversations/${conversationId}${suffix}`, {
    signal: options?.signal,
  });
}

export function fetchConversationMessages(
  conversationId: number,
  options: {
    beforeMessageId: number;
    limit?: number;
    signal?: AbortSignal;
  },
) {
  const params = new URLSearchParams({
    before_message_id: String(options.beforeMessageId),
  });
  if (options.limit != null) {
    params.set("limit", String(options.limit));
  }

  return apiFetch<ConversationMessagePage>(
    `/api/conversations/${conversationId}/messages?${params.toString()}`,
    { signal: options.signal },
  );
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
  await assertApiResponse(response);
}

export function updateMessageFeedback(messageId: number, value: FeedbackValue | null) {
  return apiFetch<{ id: number; feedback: FeedbackValue | null }>(`/api/chat/messages/${messageId}/feedback`, {
    method: "PATCH",
    body: JSON.stringify({ value }),
  });
}

export function fetchMessagePendingMemories(messageId: number) {
  return apiFetch<MemoryItem[]>(`/api/chat/messages/${messageId}/pending-memories`);
}

export function confirmPendingMemory(memoryId: number, payload?: MemoryCandidateUpdatePayload) {
  return apiFetch<MemoryItem>(`/api/chat/memories/${memoryId}/confirm`, {
    method: "POST",
    body: payload ? JSON.stringify(payload) : undefined,
  });
}

export function rejectPendingMemory(memoryId: number) {
  return apiFetch<MemoryItem>(`/api/chat/memories/${memoryId}/reject`, {
    method: "POST",
  });
}
