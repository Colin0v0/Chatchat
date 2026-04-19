import type {
  DebateActiveRun,
  DebateAskRequest,
  DebateDecisionRequest,
  DebateFreeDebateState,
  DebateJudgeDecision,
  DebateParticipant,
  DebateSessionCreateRequest,
  DebateSessionDetail,
  DebateSessionSummary,
  DebateStreamEvent,
  DebateTurn,
} from "../../../types";
import { apiFetch, assertApiResponse, toApiUrl } from "../../../shared/api/http";
import { consumeNdjsonStream } from "../../../shared/api/ndjson";

export interface DebateStreamRequestOptions {
  onEvent: (event: DebateStreamEvent) => void;
  signal?: AbortSignal;
  batchWindowMs?: number;
  runId?: string | null;
  afterSeq?: number | null;
}

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

function normalizeDebateAiSuggestion(value: unknown): DebateAiSuggestion | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const payload = value as Record<string, unknown>;
  return {
    winner:
      payload.winner === "pro" || payload.winner === "con" || payload.winner === "draw"
        ? payload.winner
        : "draw",
    pro_score:
      typeof payload.pro_score === "number" && Number.isFinite(payload.pro_score)
        ? payload.pro_score
        : null,
    con_score:
      typeof payload.con_score === "number" && Number.isFinite(payload.con_score)
        ? payload.con_score
        : null,
    judge_comment: typeof payload.judge_comment === "string" ? payload.judge_comment : "",
    scoring_json:
      payload.scoring_json && typeof payload.scoring_json === "object"
        ? (payload.scoring_json as Record<string, unknown>)
        : {},
  };
}

function normalizeDebateActiveRun(value: unknown): DebateActiveRun | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const payload = value as Record<string, unknown>;
  return {
    action:
      payload.action === "ask" || payload.action === "decision"
        ? payload.action
        : "next",
    started_at: typeof payload.started_at === "string" ? payload.started_at : null,
    run_id: typeof payload.run_id === "string" ? payload.run_id : null,
    last_seq:
      typeof payload.last_seq === "number" && Number.isFinite(payload.last_seq)
        ? payload.last_seq
        : null,
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
    ai_suggestion: normalizeDebateAiSuggestion(payload.ai_suggestion),
    summary: typeof payload.summary === "string" ? payload.summary : "",
    free_debate_enabled: payload.free_debate_enabled === true,
    free_debate_state: normalizeDebateFreeDebateState(payload.free_debate_state),
    active_run: normalizeDebateActiveRun(payload.active_run),
    stage_time_limits_ms: Object.fromEntries(
      Object.entries(stageTimeLimits)
        .filter(([, value]) => typeof value === "number" && Number.isFinite(value))
        .map(([key, value]) => [key, value as number]),
    ),
  };
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

export async function streamDebateNext(
  sessionId: number,
  options: DebateStreamRequestOptions,
) {
  const response = await fetch(toApiUrl(`/api/debate/sessions/${sessionId}/next`), {
    credentials: "include",
    method: "POST",
    signal: options.signal,
  });
  await assertApiResponse(response);

  await consumeNdjsonStream<DebateStreamEvent>(response, options.onEvent, options.batchWindowMs ?? 32);
}

export async function streamDebateAsk(
  sessionId: number,
  payload: DebateAskRequest,
  options: DebateStreamRequestOptions,
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

  await consumeNdjsonStream<DebateStreamEvent>(response, options.onEvent, options.batchWindowMs ?? 32);
}

export async function streamDebateDecision(
  sessionId: number,
  payload: DebateDecisionRequest,
  options: DebateStreamRequestOptions,
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

  await consumeNdjsonStream<DebateStreamEvent>(response, options.onEvent, options.batchWindowMs ?? 32);
}

export async function streamActiveDebateRun(
  sessionId: number,
  options: DebateStreamRequestOptions,
) {
  const params = new URLSearchParams();
  if (options.runId) {
    params.set("run_id", options.runId);
  }
  if (typeof options.afterSeq === "number" && Number.isFinite(options.afterSeq) && options.afterSeq >= 0) {
    params.set("after_seq", String(options.afterSeq));
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  const response = await fetch(toApiUrl(`/api/debate/sessions/${sessionId}/stream/active${suffix}`), {
    credentials: "include",
    method: "GET",
    signal: options.signal,
  });
  await assertApiResponse(response);

  await consumeNdjsonStream<DebateStreamEvent>(response, options.onEvent, options.batchWindowMs ?? 32);
}
