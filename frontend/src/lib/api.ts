import type {
  AuthSession,
  AudioTranscriptionResult,
  ChatStreamEvent,
  ChatStreamRequest,
  ConversationDetail,
  ConversationMessagePage,
  ConversationSummary,
  DebateAskRequest,
  DebateJudgeDecision,
  DebateParticipant,
  DebateFreeDebateState,
  DebateDecisionRequest,
  DebateSessionCreateRequest,
  DebateSessionDetail,
  DebateSessionSummary,
  DebateTurn,
  DebateStreamEvent,
  KnowledgeDocument,
  KnowledgeBatchDeleteResult,
  KnowledgeBatchUploadResult,
  KnowledgeReindexResult,
  KnowledgeStatus,
  MemoryCollection,
  MemoryDocument,
  MemoryItem,
  MemoryLayerCollection,
  MemoryPromotePayload,
  MemoryUpsertPayload,
  ModelOption,
  ModelsPayload,
  RegenerateChatRequest,
  FeedbackValue,
} from "../types";
import { ApiError, apiFetch, assertApiResponse, toApiUrl } from "../shared/api/http";
export { ApiError, setUnauthorizedHandler, toApiUrl } from "../shared/api/http";
export { fetchSession, login, logout } from "../features/auth/api/session";
export { fetchModels } from "../features/models/api/models";
export {
  deleteKnowledgeDocument,
  deleteKnowledgeDocuments,
  fetchKnowledgeDocuments,
  fetchKnowledgeStatus,
  reindexKnowledgeDocument,
  reindexKnowledgeDocuments,
  uploadKnowledgeDocuments,
} from "../features/knowledge/api/knowledge";
export {
  createMemory,
  deleteMemory,
  dismissMemory,
  fetchMemories,
  promoteMemory,
  updateMemory,
} from "../features/memories/api/memories";

function ensureArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function normalizeDebateParticipant(value: unknown): DebateParticipant | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const payload = value as Record<string, unknown>;
  if (typeof payload.id !== "number" || typeof payload.model_id !== "string") {
    return null;
  }

  return {
    id: payload.id,
    model_id: payload.model_id,
    side: payload.side === "con" ? "con" : "pro",
    style: typeof payload.style === "string" ? payload.style : "",
    order_index: typeof payload.order_index === "number" ? payload.order_index : 0,
  };
}

function normalizeDebateTurn(value: unknown): DebateTurn | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const payload = value as Record<string, unknown>;
  if (typeof payload.id !== "number" || typeof payload.stage !== "string") {
    return null;
  }

  const stage =
    payload.stage === "rebuttal" ||
    payload.stage === "free_debate" ||
    payload.stage === "closing" ||
    payload.stage === "judge_decision"
      ? payload.stage
      : "opening";

  return {
    id: payload.id,
    kind:
      payload.kind === "judge_question" || payload.kind === "system_note" ? payload.kind : "speaker_turn",
    stage,
    turn_index: typeof payload.turn_index === "number" ? payload.turn_index : 0,
    speaker_participant_id:
      typeof payload.speaker_participant_id === "number" ? payload.speaker_participant_id : null,
    target_turn_id: typeof payload.target_turn_id === "number" ? payload.target_turn_id : null,
    content: typeof payload.content === "string" ? payload.content : "",
    reasoning: typeof payload.reasoning === "string" ? payload.reasoning : null,
    created_at: typeof payload.created_at === "string" ? payload.created_at : null,
    elapsed_ms:
      typeof payload.elapsed_ms === "number" && Number.isFinite(payload.elapsed_ms)
        ? payload.elapsed_ms
        : null,
    truncated: payload.truncated === true,
  };
}

function normalizeDebateFreeDebateState(value: unknown): DebateFreeDebateState | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const payload = value as Record<string, unknown>;
  return {
    pro_remaining_ms:
      typeof payload.pro_remaining_ms === "number" && Number.isFinite(payload.pro_remaining_ms)
        ? payload.pro_remaining_ms
        : 0,
    con_remaining_ms:
      typeof payload.con_remaining_ms === "number" && Number.isFinite(payload.con_remaining_ms)
        ? payload.con_remaining_ms
        : 0,
    active_side: payload.active_side === "pro" || payload.active_side === "con" ? payload.active_side : null,
    active_turn_id: typeof payload.active_turn_id === "number" ? payload.active_turn_id : null,
    active_turn_started_at:
      typeof payload.active_turn_started_at === "string" ? payload.active_turn_started_at : null,
    turn_count: typeof payload.turn_count === "number" ? payload.turn_count : 0,
    ended_reason:
      payload.ended_reason === "pro_timeout" ||
      payload.ended_reason === "con_timeout" ||
      payload.ended_reason === "both_timeout" ||
      payload.ended_reason === "manual"
        ? payload.ended_reason
        : null,
  };
}

function normalizeDebateJudgeDecision(value: unknown): DebateJudgeDecision | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const payload = value as Record<string, unknown>;
  return {
    winner_side:
      payload.winner_side === "pro" || payload.winner_side === "con" || payload.winner_side === "draw"
        ? payload.winner_side
        : "draw",
    scoring_json:
      payload.scoring_json && typeof payload.scoring_json === "object"
        ? (payload.scoring_json as Record<string, unknown>)
        : {},
    judge_comment: typeof payload.judge_comment === "string" ? payload.judge_comment : "",
    created_at: typeof payload.created_at === "string" ? payload.created_at : null,
  };
}

function normalizeDebateSessionDetail(value: unknown): DebateSessionDetail {
  const payload = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const stageTimeLimits =
    payload.stage_time_limits_ms && typeof payload.stage_time_limits_ms === "object"
      ? (payload.stage_time_limits_ms as Record<string, unknown>)
      : {};

  return {
    id: typeof payload.id === "number" ? payload.id : 0,
    topic: typeof payload.topic === "string" ? payload.topic : "",
    status:
      payload.status === "running" || payload.status === "waiting_judge" || payload.status === "finished"
        ? payload.status
        : "created",
    stage:
      payload.stage === "rebuttal" ||
      payload.stage === "free_debate" ||
      payload.stage === "closing" ||
      payload.stage === "judge_decision"
        ? payload.stage
        : "opening",
    created_at: typeof payload.created_at === "string" ? payload.created_at : null,
    updated_at: typeof payload.updated_at === "string" ? payload.updated_at : null,
    finished_at: typeof payload.finished_at === "string" ? payload.finished_at : null,
    participants: ensureArray<unknown>(payload.participants)
      .map(normalizeDebateParticipant)
      .filter((participant): participant is DebateParticipant => participant != null),
    turns: ensureArray<unknown>(payload.turns)
      .map(normalizeDebateTurn)
      .filter((turn): turn is DebateTurn => turn != null),
    judge_decision: normalizeDebateJudgeDecision(payload.judge_decision),
    summary: typeof payload.summary === "string" ? payload.summary : "",
    free_debate_enabled: payload.free_debate_enabled === true,
    free_debate_state: normalizeDebateFreeDebateState(payload.free_debate_state),
    stage_time_limits_ms: Object.fromEntries(
      Object.entries(stageTimeLimits)
        .filter(([, value]) => typeof value === "number" && Number.isFinite(value))
        .map(([key, value]) => [key, value as number]),
    ),
  };
}

export function fetchConversations() {
  return apiFetch<ConversationSummary[]>("/api/conversations");
}

export async function fetchDebateSessions() {
  const sessions = await apiFetch<DebateSessionSummary[]>("/api/debate/sessions");
  return sessions.map((session) => ({
    ...session,
    last_turn_preview: session.last_turn_preview ?? "",
  }));
}

export async function createDebateSession(payload: DebateSessionCreateRequest) {
  const session = await apiFetch<unknown>("/api/debate/sessions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return normalizeDebateSessionDetail(session);
}

export async function fetchDebateSession(sessionId: number) {
  const session = await apiFetch<unknown>(`/api/debate/sessions/${sessionId}`);
  return normalizeDebateSessionDetail(session);
}

export function renameDebateSession(sessionId: number, topic: string) {
  return apiFetch<DebateSessionSummary>(`/api/debate/sessions/${sessionId}`, {
    method: "PATCH",
    body: JSON.stringify({ topic }),
  });
}

export async function deleteDebateSession(sessionId: number) {
  const response = await fetch(toApiUrl(`/api/debate/sessions/${sessionId}`), {
    credentials: "include",
    method: "DELETE",
  });
  await assertApiResponse(response);
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

interface StreamRequestOptions {
  onEvent: (event: ChatStreamEvent) => void;
  signal?: AbortSignal;
  batchWindowMs?: number;
}

interface GenericStreamRequestOptions<TEvent> {
  onEvent: (event: TEvent) => void;
  signal?: AbortSignal;
  batchWindowMs?: number;
}

function parseNdjsonEvent<TEvent>(raw: string): TEvent | null {
  const trimmed = raw.trim();
  if (!trimmed) {
    return null;
  }

  try {
    return JSON.parse(trimmed) as TEvent;
  } catch (err) {
    console.warn("[ndjson parse error]", trimmed.substring(0, 100), err);
    return null;
  }
}

function createBatchedEventDispatcher<TEvent>(
  onEvent: (event: TEvent) => void,
  batchWindowMs = 0,
) {
  let timerId: number | null = null;
  let pendingEvents: TEvent[] = [];

  const flush = () => {
    timerId = null;
    if (!pendingEvents.length) {
      return;
    }
    const batch = pendingEvents;
    pendingEvents = [];
    for (const event of batch) {
      onEvent(event);
    }
  };

  return {
    dispatch(event: TEvent) {
      if (batchWindowMs <= 0) {
        onEvent(event);
        return;
      }
      pendingEvents.push(event);
      if (timerId !== null) {
        return;
      }
      timerId = window.setTimeout(flush, batchWindowMs);
    },
    finish() {
      if (timerId !== null) {
        window.clearTimeout(timerId);
        timerId = null;
      }
      flush();
    },
  };
}

async function consumeNdjsonStream<TEvent>(
  response: Response,
  onEvent: (event: TEvent) => void,
  batchWindowMs = 0,
) {
  if (!response.body) {
    throw new Error("Streaming is not supported by this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const dispatcher = createBatchedEventDispatcher(onEvent, batchWindowMs);
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const event = parseNdjsonEvent<TEvent>(line);
        if (event) {
          dispatcher.dispatch(event);
        }
      }
    }

    buffer += decoder.decode();
    const tailEvent = parseNdjsonEvent<TEvent>(buffer);
    if (tailEvent) {
      dispatcher.dispatch(tailEvent);
    }
  } finally {
    dispatcher.finish();
  }
}

function audioExtensionForMimeType(mimeType: string): string {
  const normalized = mimeType.toLowerCase();
  if (normalized.startsWith("audio/mp4")) {
    return ".mp4";
  }
  if (
    normalized.startsWith("audio/wav") ||
    normalized.startsWith("audio/wave") ||
    normalized.startsWith("audio/x-wav")
  ) {
    return ".wav";
  }
  return ".webm";
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
  await assertApiResponse(response);
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
  formData.append("tool_mode", payload.tool_mode);
  if (payload.reasoning_profile) {
    formData.append("reasoning_profile", payload.reasoning_profile);
  }
  payload.files?.forEach((file) => formData.append("files", file));

  const response = await fetch(toApiUrl("/api/chat/stream"), {
    credentials: "include",
    method: "POST",
    body: formData,
    signal: options.signal,
  });
  await assertApiResponse(response);

  await consumeNdjsonStream(response, options.onEvent, options.batchWindowMs);
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
  await assertApiResponse(response);

  await consumeNdjsonStream(response, options.onEvent, options.batchWindowMs);
}

export async function streamDebateNext(
  sessionId: number,
  options: GenericStreamRequestOptions<DebateStreamEvent>,
) {
  const response = await fetch(toApiUrl(`/api/debate/sessions/${sessionId}/next`), {
    credentials: "include",
    method: "POST",
    signal: options.signal,
  });
  await assertApiResponse(response);

  await consumeNdjsonStream(response, options.onEvent, options.batchWindowMs ?? 32);
}

export async function streamDebateAsk(
  sessionId: number,
  payload: DebateAskRequest,
  options: GenericStreamRequestOptions<DebateStreamEvent>,
) {
  const response = await fetch(toApiUrl(`/api/debate/sessions/${sessionId}/judge/ask`), {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  await assertApiResponse(response);

  await consumeNdjsonStream(response, options.onEvent, options.batchWindowMs ?? 32);
}

export async function streamDebateDecision(
  sessionId: number,
  payload: DebateDecisionRequest,
  options: GenericStreamRequestOptions<DebateStreamEvent>,
) {
  const response = await fetch(toApiUrl(`/api/debate/sessions/${sessionId}/judge/decision`), {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  await assertApiResponse(response);

  await consumeNdjsonStream(response, options.onEvent, options.batchWindowMs ?? 32);
}

export function updateMessageFeedback(messageId: number, value: FeedbackValue | null) {
  return apiFetch<{ id: number; feedback: FeedbackValue | null }>(`/api/chat/messages/${messageId}/feedback`, {
    method: "PATCH",
    body: JSON.stringify({ value }),
  });
}
