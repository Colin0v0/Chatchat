import type {
  DebateJudgeAnalysis,
  DebateSessionDetail,
  DebateStageScoreKey,
  DebateStreamEvent,
  DebateTurn,
  DebateWinner,
} from "../../types";
import { JUDGE_STAGE_SCORE_KEYS, JUDGE_STAGE_SCORE_LABEL } from "./debateRoomConstants";

export function normalizeRoomSession(session: DebateSessionDetail): DebateSessionDetail {
  return {
    ...session,
    participants: Array.isArray(session.participants) ? session.participants : [],
    turns: Array.isArray(session.turns) ? session.turns : [],
    judge_decision: session.judge_decision ?? null,
    summary: typeof session.summary === "string" ? session.summary : "",
    free_debate_enabled: session.free_debate_enabled === true,
    free_debate_state: session.free_debate_state ?? null,
    stage_time_limits_ms:
      session.stage_time_limits_ms && typeof session.stage_time_limits_ms === "object"
        ? session.stage_time_limits_ms
        : {},
  };
}

export function formatClock(ms: number) {
  const safeMs = Math.max(0, ms);
  const totalSeconds = Math.floor(safeMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  const tenths = Math.floor((safeMs % 1000) / 100);
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${tenths}`;
}

export function parseUtcTimestamp(value: string | null | undefined) {
  if (!value) {
    return Number.NaN;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return Number.NaN;
  }

  const withTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(trimmed) ? trimmed : `${trimmed}Z`;
  const normalized = withTimezone.replace(
    /\.(\d{3})\d+(Z|[+-]\d{2}:\d{2})$/i,
    ".$1$2",
  );
  return Date.parse(normalized);
}

export function normalizeWinnerSide(
  winner: DebateWinner | null | undefined,
  scoring?: Record<string, unknown> | null,
): DebateWinner {
  const proScore =
    typeof scoring?.pro_score === "number" && Number.isFinite(scoring.pro_score)
      ? scoring.pro_score
      : null;
  const conScore =
    typeof scoring?.con_score === "number" && Number.isFinite(scoring.con_score)
      ? scoring.con_score
      : null;

  if (proScore != null && conScore != null && proScore !== conScore) {
    return proScore > conScore ? "pro" : "con";
  }

  if (winner === "pro" || winner === "con") {
    return winner;
  }

  return "pro";
}

export function upsertTurn(turns: DebateTurn[], nextTurn: DebateTurn) {
  const existingIndex = turns.findIndex((turn) => turn.id === nextTurn.id);
  if (existingIndex === -1) {
    return [...turns, nextTurn].sort((left, right) => left.turn_index - right.turn_index);
  }

  return turns.map((turn, index) => (index === existingIndex ? nextTurn : turn));
}

export function patchTurn(
  turns: DebateTurn[],
  turnId: number,
  patch: (turn: DebateTurn) => DebateTurn,
) {
  return turns.map((turn) => (turn.id === turnId ? patch(turn) : turn));
}

export function applyStreamEvent(
  session: DebateSessionDetail,
  event: DebateStreamEvent,
): DebateSessionDetail {
  const normalizedSession = normalizeRoomSession(session);

  switch (event.type) {
    case "stage_changed":
      return {
        ...normalizedSession,
        stage: event.stage,
        status: event.status,
      };
    case "judge_question":
    case "meta":
      return {
        ...normalizedSession,
        turns: upsertTurn(normalizedSession.turns, event.turn),
      };
    case "token":
      return {
        ...normalizedSession,
        turns: patchTurn(normalizedSession.turns, event.turn_id, (turn) => ({
          ...turn,
          content: `${turn.content}${event.content}`,
        })),
      };
    case "reasoning":
      return {
        ...normalizedSession,
        turns: patchTurn(normalizedSession.turns, event.turn_id, (turn) => ({
          ...turn,
          reasoning: `${turn.reasoning ?? ""}${event.content}`,
        })),
      };
    case "turn_done":
      return {
        ...normalizedSession,
        turns: upsertTurn(normalizedSession.turns, event.turn),
      };
    case "decision_saved":
      return {
        ...normalizedSession,
        judge_decision: event.judge_decision,
        status: event.status,
        stage: event.stage,
      };
    case "summary_token":
      return {
        ...normalizedSession,
        summary: (normalizedSession.summary ?? "") + event.content,
      };
    case "judge_analysis_token":
      return normalizedSession;
    case "free_debate_clock":
      return {
        ...normalizedSession,
        free_debate_state: event.state,
      };
    case "done":
      return {
        ...normalizedSession,
        stage: event.stage,
        status: event.status,
      };
    case "ai_suggestion":
    case "error":
      return normalizedSession;
  }
}

export function scoreValue(score: unknown) {
  return typeof score === "number" && Number.isFinite(score) ? String(score) : "";
}

function toFiniteScore(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function stageScoreEntry(scoringJson: Record<string, unknown>, key: DebateStageScoreKey) {
  const stageScores =
    scoringJson.stage_scores && typeof scoringJson.stage_scores === "object"
      ? (scoringJson.stage_scores as Record<string, unknown>)
      : {};
  const entry =
    stageScores[key] && typeof stageScores[key] === "object"
      ? (stageScores[key] as Record<string, unknown>)
      : {};

  return {
    key,
    label: JUDGE_STAGE_SCORE_LABEL[key],
    pro: toFiniteScore(entry.pro),
    con: toFiniteScore(entry.con),
  };
}

export function extractStageScores(scoringJson: Record<string, unknown> | null | undefined) {
  if (!scoringJson || typeof scoringJson !== "object") {
    return [];
  }

  return JUDGE_STAGE_SCORE_KEYS.map((key) => stageScoreEntry(scoringJson, key)).filter(
    (item) => item.pro != null || item.con != null,
  );
}

function readAnalysisText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

export function extractJudgeAnalysisMarkdown(scoringJson: Record<string, unknown> | null | undefined) {
  return typeof scoringJson?.analysis_markdown === "string" ? scoringJson.analysis_markdown.trim() : "";
}

export function extractJudgeAnalysis(
  scoringJson: Record<string, unknown> | null | undefined,
): DebateJudgeAnalysis {
  const analysis =
    scoringJson?.analysis && typeof scoringJson.analysis === "object"
      ? (scoringJson.analysis as Record<string, unknown>)
      : {};

  const proScore =
    typeof scoringJson?.pro_score === "number" && Number.isFinite(scoringJson.pro_score)
      ? scoringJson.pro_score
      : null;
  const conScore =
    typeof scoringJson?.con_score === "number" && Number.isFinite(scoringJson.con_score)
      ? scoringJson.con_score
      : null;
  const resolvedVote =
    proScore != null && conScore != null && proScore !== conScore
      ? proScore > conScore
        ? "本场我投正方一票"
        : "本场我投反方一票"
      : "";

  return {
    pro_review: readAnalysisText(analysis.pro_review ?? analysis.pro),
    con_review: readAnalysisText(analysis.con_review ?? analysis.con),
    shared_feedback: readAnalysisText(analysis.shared_feedback ?? analysis.both),
    key_decision: readAnalysisText(analysis.key_decision ?? analysis.key_point),
    final_vote: resolvedVote || readAnalysisText(analysis.final_vote ?? analysis.vote),
  };
}
