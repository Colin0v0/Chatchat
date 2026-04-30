import type {
  MemoryCollection,
  MemoryDocument,
  MemoryItem,
  MemoryLayerCollection,
  MemoryUpsertPayload,
} from "../../../types";
import { apiFetch, assertApiResponse, toApiUrl } from "../../../shared/api/http";

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
    payload.status === "active" || payload.status === "archived"
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
  return {
    documents: normalizeMemoryDocuments(payload.documents),
    active_items: normalizeMemoryLayerCollection(payload.active_items),
  };
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

export async function deleteMemory(memoryId: number) {
  const response = await fetch(toApiUrl(`/api/memories/items/${memoryId}`), {
    credentials: "include",
    method: "DELETE",
  });
  await assertApiResponse(response);
}
