import type {
  BattleSessionSummary,
  BattleStreamRequest,
  ChatStreamEvent,
} from "../../../types";
import { apiFetch, assertApiResponse, toApiUrl } from "../../../shared/api/http";
import { consumeNdjsonStream } from "../../../shared/api/ndjson";
import type { BattleSessionDetail } from "../model/types";

export interface BattleStreamOptions {
  onEvent: (event: ChatStreamEvent) => void;
  signal?: AbortSignal;
}

export async function streamBattleResponse(payload: BattleStreamRequest, options: BattleStreamOptions) {
  const formData = new FormData();
  formData.append("message", payload.message);
  formData.append("model", payload.model);
  formData.append("tool_mode", payload.tool_mode);
  if (payload.history && payload.history.length > 0) {
    formData.append("history", JSON.stringify(payload.history));
  }
  payload.knowledge_folders?.forEach((folder) => formData.append("knowledge_folders", folder));
  if (payload.reasoning_profile) {
    formData.append("reasoning_profile", payload.reasoning_profile);
  }
  payload.files?.forEach((file) => formData.append("files", file));

  const response = await fetch(toApiUrl("/api/battle/stream"), {
    credentials: "include",
    method: "POST",
    body: formData,
    signal: options.signal,
  });
  await assertApiResponse(response);

  await consumeNdjsonStream<ChatStreamEvent>(response, options.onEvent);
}

export function fetchBattleSessions(signal?: AbortSignal) {
  return apiFetch<BattleSessionSummary[]>("/api/battle/sessions", { signal });
}

export function fetchBattleSession(sessionId: number, signal?: AbortSignal) {
  return apiFetch<BattleSessionDetail>(`/api/battle/sessions/${sessionId}`, { signal });
}

export function createBattleSession(payload: Pick<BattleSessionDetail, "title" | "rounds">) {
  return apiFetch<BattleSessionDetail>("/api/battle/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateBattleSession(sessionId: number, payload: Pick<BattleSessionDetail, "title" | "rounds">) {
  return apiFetch<BattleSessionDetail>(`/api/battle/sessions/${sessionId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function renameBattleSession(sessionId: number, title: string) {
  return apiFetch<BattleSessionSummary>(`/api/battle/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export async function deleteBattleSession(sessionId: number) {
  const response = await fetch(toApiUrl(`/api/battle/sessions/${sessionId}`), {
    credentials: "include",
    method: "DELETE",
  });
  await assertApiResponse(response);
}
