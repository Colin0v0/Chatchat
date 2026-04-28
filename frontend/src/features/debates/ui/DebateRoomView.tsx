import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { streamActiveDebateRun, streamDebateAsk, streamDebateDecision, streamDebateNext } from "../api/debates";
import type {
  DebateAiSuggestion,
  DebateAskTarget,
  DebateSessionDetail,
  DebateStage,
  DebateStreamEvent,
  DebateWinner,
} from "../../../types";
import { FLOW_STEPS, STAGE_LABEL, WINNER_LABEL } from "../lib/debateRoomConstants";
import {
  applyStreamEvent,
  extractJudgeAnalysis,
  extractJudgeAnalysisMarkdown,
  extractStageScores,
  normalizeRoomSession,
  normalizeWinnerSide,
  parseUtcTimestamp,
  scoreValue,
} from "../lib/debateRoomUtils";
import { DebateControls } from "./room/DebateControls";
import { DebateStageHeader } from "./room/DebateBadges";
import { DebateJudgeCard } from "./room/DebateJudgeCard";
import { DebateTurnCard } from "./room/DebateTurnCard";
import { ApiError } from "../../../shared/api/http";

const FREE_DEBATE_CLOCK_SKEW_TOLERANCE_MS = 10 * 60 * 1000;

function resolveFreeDebateClockAnchorMs(
  state: DebateSessionDetail["free_debate_state"] | null | undefined,
) {
  if (!state?.active_side || state.active_turn_id == null) {
    return null;
  }

  const parsedStartedAt = parseUtcTimestamp(state.active_turn_started_at);
  const now = Date.now();
  if (Number.isFinite(parsedStartedAt) && Math.abs(now - parsedStartedAt) <= FREE_DEBATE_CLOCK_SKEW_TOLERANCE_MS) {
    return parsedStartedAt;
  }

  return now;
}

function stageBudgetMs(session: DebateSessionDetail, stage: DebateStage) {
  return typeof session.stage_time_limits_ms?.[stage] === "number"
    ? session.stage_time_limits_ms[stage]
    : 0;
}

function resolveResumableStreamingTurn(session: DebateSessionDetail) {
  if (session.stage === "free_debate") {
    return {
      turnId: session.free_debate_state?.active_turn_id ?? null,
      startedAtMs: resolveFreeDebateClockAnchorMs(session.free_debate_state),
    };
  }

  if (session.status !== "running") {
    return {
      turnId: null,
      startedAtMs: null,
    };
  }

  const pendingTurn = [...session.turns]
    .filter(
      (turn) =>
        turn.kind === "speaker_turn"
        && turn.stage === session.stage
        && turn.elapsed_ms == null,
    )
    .sort((left, right) =>
      left.turn_index === right.turn_index
        ? String(left.created_at ?? "").localeCompare(String(right.created_at ?? ""))
        : left.turn_index - right.turn_index,
    );
  const lastPendingTurnIndex = pendingTurn.length - 1;
  const currentPendingTurn = lastPendingTurnIndex >= 0 ? pendingTurn[lastPendingTurnIndex] : null;

  if (!currentPendingTurn || typeof currentPendingTurn.id !== "number") {
    return {
      turnId: null,
      startedAtMs: null,
    };
  }

  const parsedStartedAt = parseUtcTimestamp(currentPendingTurn.answer_started_at);
  return {
    turnId: currentPendingTurn.id,
    startedAtMs: Number.isFinite(parsedStartedAt) ? parsedStartedAt : null,
  };
}

function toDecisionWinner(winner: DebateWinner | null | undefined): "pro" | "con" {
  return winner === "con" ? "con" : "pro";
}

function toNumericScore(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function stageScoresMatchTotals(scoringJson: Record<string, unknown>, proScore: number | null, conScore: number | null) {
  const stageScores = extractStageScores(scoringJson);
  if (!stageScores.length) {
    return true;
  }

  const proTotal = stageScores.reduce((sum, item) => sum + (item.pro ?? 0), 0);
  const conTotal = stageScores.reduce((sum, item) => sum + (item.con ?? 0), 0);

  return (proScore == null || proScore === proTotal) && (conScore == null || conScore === conTotal);
}

function buildDecisionScoringJson(
  base: Record<string, unknown> | null | undefined,
  proScoreValue: string,
  conScoreValue: string,
) {
  const next: Record<string, unknown> = { ...(base ?? {}) };
  const proScore = toNumericScore(proScoreValue);
  const conScore = toNumericScore(conScoreValue);

  if (proScore != null) {
    next.pro_score = proScore;
  } else {
    delete next.pro_score;
  }

  if (conScore != null) {
    next.con_score = conScore;
  } else {
    delete next.con_score;
  }

  if (!stageScoresMatchTotals(next, proScore, conScore)) {
    delete next.stage_scores;
  }

  return next;
}

function suggestionAnalysisMarkdown(suggestion: DebateAiSuggestion | null | undefined) {
  return extractJudgeAnalysisMarkdown(
    suggestion?.scoring_json as Record<string, unknown> | null | undefined,
  );
}

function debateActiveRunKey(
  sessionId: number,
  activeRun: DebateSessionDetail["active_run"] | null | undefined,
) {
  if (!activeRun) {
    return null;
  }

  if (typeof activeRun.run_id === "string" && activeRun.run_id.trim()) {
    return activeRun.run_id.trim();
  }

  return `${sessionId}:${activeRun.action}:${activeRun.started_at ?? "none"}`;
}

export function DebateRoomView({
  session,
  isSessionRunning = false,
  onRefresh,
  onActivityChange,
  onSessionSnapshot,
  transientState,
  onTransientStateChange,
  onStreamEvent,
  onSessionChange,
}: {
  session: DebateSessionDetail;
  isSessionRunning?: boolean;
  onRefresh: (sessionId: number) => Promise<DebateSessionDetail>;
  onActivityChange?: (sessionId: number, activity: { running: boolean; unread: boolean }) => void;
  onSessionSnapshot?: (session: DebateSessionDetail) => void;
  transientState?: {
    aiSuggestion: DebateAiSuggestion | null;
    judgeAnalysisStream: string;
    runKey?: string | null;
    lastSeq?: number | null;
  } | null;
  onTransientStateChange?: (
    sessionId: number,
    patch: Partial<{
      aiSuggestion: DebateAiSuggestion | null;
      judgeAnalysisStream: string;
      runKey: string | null;
      lastSeq: number | null;
    }> | null,
  ) => void;
  onStreamEvent?: (sessionId: number, event: DebateStreamEvent) => void;
  onSessionChange: (session: DebateSessionDetail) => void;
}) {
  const [roomSession, setRoomSession] = useState(() => normalizeRoomSession(session));
  const [askTarget, setAskTarget] = useState<DebateAskTarget>("all");
  const [askQuestion, setAskQuestion] = useState("");
  const [winner, setWinner] = useState<"pro" | "con">(
    toDecisionWinner(
      normalizeWinnerSide(session.judge_decision?.winner_side, session.judge_decision?.scoring_json),
    ),
  );
  const [judgeComment, setJudgeComment] = useState(session.judge_decision?.judge_comment ?? "");
  const [proScore, setProScore] = useState(scoreValue(session.judge_decision?.scoring_json?.pro_score));
  const [conScore, setConScore] = useState(scoreValue(session.judge_decision?.scoring_json?.con_score));
  const [runningAction, setRunningAction] = useState<"next" | "ask" | "decision" | null>(null);
  const runningActionRef = useRef<"next" | "ask" | "decision" | null>(null);
  const lastSessionIdRef = useRef(session.id);
  const [actionError, setActionError] = useState<string | null>(null);
  const [aiSuggestion, setAiSuggestion] = useState<DebateAiSuggestion | null>(
    transientState?.aiSuggestion ?? session.ai_suggestion ?? null,
  );
  const [activeStreamingTurnId, setActiveStreamingTurnId] = useState<number | null>(() => {
    const resumed = resolveResumableStreamingTurn(normalizeRoomSession(session));
    return resumed.turnId;
  });
  const [activeStreamingTurnStartedAtMs, setActiveStreamingTurnStartedAtMs] = useState<number | null>(() => {
    const resumed = resolveResumableStreamingTurn(normalizeRoomSession(session));
    return resumed.startedAtMs;
  });
  const [freeDebateClockAnchor, setFreeDebateClockAnchor] = useState<{
    turnId: number | null;
    startedAtMs: number | null;
  }>(() => ({
    turnId: session.free_debate_state?.active_turn_id ?? null,
    startedAtMs: resolveFreeDebateClockAnchorMs(session.free_debate_state),
  }));
  const [clockNow, setClockNow] = useState(() => Date.now());
  const [judgeExpanded, setJudgeExpanded] = useState(true);
  const [judgeAnalysisStream, setJudgeAnalysisStream] = useState(transientState?.judgeAnalysisStream ?? "");
  const latestRoomSessionRef = useRef(roomSession);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const pendingScrollToBottomSessionRef = useRef<number | null>(null);
  const requestControllersRef = useRef<Set<AbortController>>(new Set());
  const attachedRunKeyRef = useRef<string | null>(null);
  const pendingReplayResetRunKeyRef = useRef<string | null>(null);
  const streamEpochRef = useRef(0);
  const applySessionStreamEvent = useCallback(
    (event: DebateStreamEvent) => {
      setRoomSession((current) => applyStreamEvent(current, event));
      onStreamEvent?.(session.id, event);
    },
    [onStreamEvent, session.id],
  );

  useEffect(() => {
    latestRoomSessionRef.current = roomSession;
  }, [roomSession]);

  const abortOpenRequests = useCallback(() => {
    streamEpochRef.current += 1;
    const controllers = [...requestControllersRef.current];
    requestControllersRef.current.clear();
    for (const controller of controllers) {
      controller.abort();
    }
    attachedRunKeyRef.current = null;
    runningActionRef.current = null;
  }, []);

  useEffect(() => {
    return () => {
      onSessionSnapshot?.(latestRoomSessionRef.current);
    };
  }, [onSessionSnapshot, session.id]);

  useEffect(() => {
    return () => {
      abortOpenRequests();
    };
  }, [abortOpenRequests, session.id]);

  useEffect(() => {
    const activeRunKey = debateActiveRunKey(roomSession.id, roomSession.active_run);
    const transientMatchesActiveRun =
      !activeRunKey
      || !transientState?.runKey
      || transientState.runKey === activeRunKey;
    const nextSuggestion = transientMatchesActiveRun
      ? (transientState?.aiSuggestion ?? roomSession.ai_suggestion ?? null)
      : (roomSession.ai_suggestion ?? null);
    const nextAnalysisStream = transientMatchesActiveRun ? (transientState?.judgeAnalysisStream ?? "") : "";
    const nextSuggestionAnalysisMarkdown = suggestionAnalysisMarkdown(nextSuggestion);

    setAiSuggestion(nextSuggestion);
    setJudgeAnalysisStream(nextSuggestionAnalysisMarkdown ? "" : nextAnalysisStream);

    if (!nextSuggestion) {
      return;
    }

    setWinner(
      toDecisionWinner(
        normalizeWinnerSide(nextSuggestion.winner as DebateWinner, {
          pro_score: nextSuggestion.pro_score,
          con_score: nextSuggestion.con_score,
        }),
      ),
    );
    if (nextSuggestion.pro_score != null) {
      setProScore(String(nextSuggestion.pro_score));
    }
    if (nextSuggestion.con_score != null) {
      setConScore(String(nextSuggestion.con_score));
    }
    if (nextSuggestion.judge_comment) {
      setJudgeComment(nextSuggestion.judge_comment);
    }
  }, [roomSession.active_run, roomSession.id, transientState]);

  useEffect(() => {
    if (!isSessionRunning) {
      pendingScrollToBottomSessionRef.current = null;
      return;
    }

    pendingScrollToBottomSessionRef.current = session.id;
  }, [isSessionRunning, session.id]);

  useEffect(() => {
    if (runningActionRef.current !== null) {
      return;
    }

    const normalizedSession = normalizeRoomSession(session);
    const isSameSession = lastSessionIdRef.current === session.id;
    lastSessionIdRef.current = session.id;
    const resumedStreamingTurn = resolveResumableStreamingTurn(normalizedSession);

    setRoomSession(normalizedSession);
    setActiveStreamingTurnId(resumedStreamingTurn.turnId);
    setActiveStreamingTurnStartedAtMs(resumedStreamingTurn.startedAtMs);
    setFreeDebateClockAnchor({
      turnId: normalizedSession.free_debate_state?.active_turn_id ?? null,
      startedAtMs: resolveFreeDebateClockAnchorMs(normalizedSession.free_debate_state),
    });
    setJudgeAnalysisStream(
      suggestionAnalysisMarkdown(transientState?.aiSuggestion)
        ? ""
        : transientState?.judgeAnalysisStream
          ?? extractJudgeAnalysisMarkdown(
            normalizedSession.judge_decision?.scoring_json as Record<string, unknown> | undefined,
          ),
    );

    if (normalizedSession.judge_decision) {
      setAiSuggestion(null);
      onTransientStateChange?.(session.id, null);
      setWinner(
        toDecisionWinner(
          normalizeWinnerSide(
            normalizedSession.judge_decision.winner_side,
            normalizedSession.judge_decision.scoring_json,
          ),
        ),
      );
      setJudgeComment(normalizedSession.judge_decision.judge_comment ?? "");
      setProScore(scoreValue(normalizedSession.judge_decision.scoring_json?.pro_score));
      setConScore(scoreValue(normalizedSession.judge_decision.scoring_json?.con_score));
      return;
    }

    if (isSameSession) {
      return;
    }

    const activeRunKey = debateActiveRunKey(normalizedSession.id, normalizedSession.active_run);
    const transientMatchesActiveRun =
      !activeRunKey
      || !transientState?.runKey
      || transientState.runKey === activeRunKey;
    const nextSuggestion = transientMatchesActiveRun
      ? (transientState?.aiSuggestion ?? normalizedSession.ai_suggestion ?? null)
      : (normalizedSession.ai_suggestion ?? null);
    setAiSuggestion(nextSuggestion);

    if (nextSuggestion) {
      setWinner(
        toDecisionWinner(
          normalizeWinnerSide(nextSuggestion.winner as DebateWinner, {
            pro_score: nextSuggestion.pro_score,
            con_score: nextSuggestion.con_score,
          }),
        ),
      );
      setJudgeComment(nextSuggestion.judge_comment ?? "");
      setProScore(nextSuggestion.pro_score != null ? String(nextSuggestion.pro_score) : "");
      setConScore(nextSuggestion.con_score != null ? String(nextSuggestion.con_score) : "");
      return;
    }

    setWinner("pro");
    setJudgeComment("");
    setProScore("");
    setConScore("");
  }, [onTransientStateChange, session, transientState]);

  useEffect(() => {
    setFreeDebateClockAnchor((current) => {
      const state = roomSession.free_debate_state;
      if (!state?.active_side || state.active_turn_id == null) {
        return current.turnId == null && current.startedAtMs == null
          ? current
          : { turnId: null, startedAtMs: null };
      }

      if (current.turnId === state.active_turn_id && current.startedAtMs != null) {
        return current;
      }

      return {
        turnId: state.active_turn_id,
        startedAtMs: resolveFreeDebateClockAnchorMs(state),
      };
    });
  }, [
    roomSession.free_debate_state?.active_side,
    roomSession.free_debate_state?.active_turn_id,
    roomSession.free_debate_state?.active_turn_started_at,
  ]);

  const participantMap = useMemo(
    () => new Map(roomSession.participants.map((participant) => [participant.id, participant])),
    [roomSession.participants],
  );
  const proParticipants = useMemo(
    () => roomSession.participants.filter((participant) => participant.side === "pro"),
    [roomSession.participants],
  );
  const conParticipants = useMemo(
    () => roomSession.participants.filter((participant) => participant.side === "con"),
    [roomSession.participants],
  );
  const sortedTurns = useMemo(
    () =>
      [...roomSession.turns].sort((left, right) =>
        left.turn_index === right.turn_index
          ? String(left.created_at ?? "").localeCompare(String(right.created_at ?? ""))
          : left.turn_index - right.turn_index,
      ),
    [roomSession.turns],
  );
  const freeDebateSequenceByTurnId = useMemo(() => {
    const sequenceMap = new Map<number | string, number>();
    let sequence = 0;

    for (const turn of sortedTurns) {
      if (turn.kind !== "speaker_turn" || turn.stage !== "free_debate") {
        continue;
      }
      sequence += 1;
      sequenceMap.set(turn.id, sequence);
    }

    return sequenceMap;
  }, [sortedTurns]);

  const sessionHasActiveRun = roomSession.active_run !== null;
  const canAdvance =
    runningAction === null &&
    !isSessionRunning &&
    !sessionHasActiveRun &&
    roomSession.status !== "finished" &&
    (roomSession.stage === "judge_decision" || roomSession.judge_decision === null);
  const canAsk =
    runningAction === null &&
    !isSessionRunning &&
    !sessionHasActiveRun &&
    roomSession.status !== "finished";
  const currentStepIndex = FLOW_STEPS.findIndex((step) => step.stage === roomSession.stage);
  const hasTurns = sortedTurns.length > 0;
  const freeDebateState = roomSession.free_debate_state;
  const proModelLabel = proParticipants[0]?.model_id ?? "";
  const conModelLabel = conParticipants[0]?.model_id ?? "";
  const activeTimedTurn = useMemo(
    () =>
      activeStreamingTurnId == null
        ? null
        : roomSession.turns.find(
            (turn) => turn.id === activeStreamingTurnId && turn.kind === "speaker_turn",
          ) ?? null,
    [activeStreamingTurnId, roomSession.turns],
  );
  const stageFixedBudgetMs = stageBudgetMs(roomSession, roomSession.stage);
  const showStageTimer = roomSession.stage !== "judge_decision";

  useEffect(() => {
    const hasFreeDebateTicker =
      !!freeDebateState?.active_side && !!freeDebateState.active_turn_started_at;
    const hasStageTicker =
      roomSession.stage !== "free_debate" &&
      activeTimedTurn != null &&
      activeStreamingTurnStartedAtMs != null &&
      stageBudgetMs(roomSession, activeTimedTurn.stage) > 0;

    if (!hasFreeDebateTicker && !hasStageTicker) {
      return;
    }

    setClockNow(Date.now());
    const timerId = window.setInterval(() => setClockNow(Date.now()), 100);
    return () => window.clearInterval(timerId);
  }, [
    activeTimedTurn,
    activeStreamingTurnStartedAtMs,
    freeDebateState?.active_side,
    freeDebateState?.active_turn_started_at,
    roomSession.stage,
  ]);

  const displayedRemainingMs = useCallback(
    (side: "pro" | "con") => {
      if (roomSession.stage === "free_debate") {
        const state = freeDebateState;
        if (!state) {
          return 0;
        }

        const base = side === "pro" ? state.pro_remaining_ms : state.con_remaining_ms;
        if (state.active_side !== side || !state.active_turn_started_at) {
          return base;
        }

        const startedAt =
          freeDebateClockAnchor.turnId === state.active_turn_id && freeDebateClockAnchor.startedAtMs != null
            ? freeDebateClockAnchor.startedAtMs
            : parseUtcTimestamp(state.active_turn_started_at);
        if (!Number.isFinite(startedAt)) {
          return base;
        }

        return Math.max(0, base - Math.max(0, clockNow - startedAt));
      }

      if (!stageFixedBudgetMs) {
        return 0;
      }
      if (!activeTimedTurn || activeTimedTurn.stage !== roomSession.stage) {
        return stageFixedBudgetMs;
      }

      const participant =
        activeTimedTurn.speaker_participant_id != null
          ? participantMap.get(activeTimedTurn.speaker_participant_id) ?? null
          : null;
      if (!participant || participant.side !== side) {
        return stageFixedBudgetMs;
      }

      if (!activeStreamingTurnStartedAtMs) {
        return stageFixedBudgetMs;
      }

      return Math.max(0, stageFixedBudgetMs - Math.max(0, clockNow - activeStreamingTurnStartedAtMs));
    },
    [
      activeStreamingTurnStartedAtMs,
      activeTimedTurn,
      clockNow,
      freeDebateClockAnchor.startedAtMs,
      freeDebateClockAnchor.turnId,
      freeDebateState,
      participantMap,
      roomSession.stage,
      stageFixedBudgetMs,
    ],
  );
  const proRemainingMs = displayedRemainingMs("pro");
  const conRemainingMs = displayedRemainingMs("con");
  const freeDebateExpiredTurnId =
    roomSession.stage === "free_debate"
    && freeDebateState?.active_turn_id != null
    && freeDebateState.active_side
    && (
      freeDebateState.active_side === "pro"
        ? proRemainingMs <= 0
        : conRemainingMs <= 0
    )
      ? freeDebateState.active_turn_id
      : null;
  const stageTurnExpired =
    roomSession.stage !== "free_debate"
    && activeTimedTurn != null
    && stageFixedBudgetMs > 0
    && activeStreamingTurnStartedAtMs != null
    && clockNow - activeStreamingTurnStartedAtMs >= stageFixedBudgetMs;
  const locallyFinalizingTurnId =
    freeDebateExpiredTurnId
    ?? (stageTurnExpired ? activeTimedTurn?.id ?? null : null);

  const syncFromServer = useCallback(async () => {
    const refreshed = await onRefresh(roomSession.id);
    setRoomSession(normalizeRoomSession(refreshed));
    return refreshed;
  }, [onRefresh, roomSession.id]);

  const updateSidebarRunning = useCallback(
    (running: boolean) => {
      onActivityChange?.(roomSession.id, {
        running,
        unread: false,
      });
    },
    [onActivityChange, roomSession.id],
  );

  const handleStreamError = useCallback((error: unknown, fallback: string) => {
    setActionError(error instanceof Error ? error.message : fallback);
  }, []);

  const beginStreamScope = useCallback(() => {
    const controller = new AbortController();
    const epoch = streamEpochRef.current + 1;
    streamEpochRef.current = epoch;
    requestControllersRef.current.add(controller);
    return { controller, epoch };
  }, []);

  const releaseRequestController = useCallback((controller: AbortController) => {
    requestControllersRef.current.delete(controller);
  }, []);

  const isCurrentStreamScope = useCallback((epoch: number) => streamEpochRef.current === epoch, []);

  const syncActiveRunProgress = useCallback((event: DebateStreamEvent) => {
    const eventRunId = typeof event.run_id === "string" && event.run_id.trim() ? event.run_id.trim() : null;
    const eventSeq = typeof event.seq === "number" && Number.isFinite(event.seq) ? event.seq : null;
    if (!eventRunId && eventSeq == null) {
      return;
    }

    setRoomSession((current) => {
      if (!current.active_run) {
        return current;
      }

      const nextRunId = eventRunId ?? current.active_run.run_id ?? null;
      const nextSeq = Math.max(current.active_run.last_seq ?? 0, eventSeq ?? 0) || null;
      if (current.active_run.run_id === nextRunId && (current.active_run.last_seq ?? null) === nextSeq) {
        return current;
      }

      return {
        ...current,
        active_run: {
          ...current.active_run,
          run_id: nextRunId,
          last_seq: nextSeq,
        },
      };
    });
  }, []);

  const markLocalActiveRun = useCallback(
    (action: "next" | "ask" | "decision") => {
      const startedAt = new Date().toISOString();
      setRoomSession((current) => ({
        ...current,
        active_run: {
          action,
          started_at: startedAt,
          run_id: null,
          last_seq: 0,
        },
      }));
      return startedAt;
    },
    [],
  );

  const handleIncomingStreamEvent = useCallback(
    (
      event: DebateStreamEvent,
      options?: {
        onJudgeAnalysis?: () => void;
        onJudgeSuggestion?: () => void;
        replayRunKey?: string;
      },
    ) => {
      const currentRun = latestRoomSessionRef.current.active_run;
      const eventRunId = typeof event.run_id === "string" && event.run_id.trim() ? event.run_id.trim() : null;
      const eventSeq = typeof event.seq === "number" && Number.isFinite(event.seq) ? event.seq : null;
      const currentRunKey = debateActiveRunKey(latestRoomSessionRef.current.id, currentRun);
      const transientSeq =
        transientState?.runKey && currentRunKey && transientState.runKey === currentRunKey
          ? transientState.lastSeq ?? 0
          : 0;
      const knownLastSeq = Math.max(currentRun?.last_seq ?? 0, transientSeq);
      if (
        eventRunId
        && currentRunKey === eventRunId
        && eventSeq != null
        && eventSeq <= knownLastSeq
      ) {
        return;
      }

      syncActiveRunProgress(event);
      if (
        options?.replayRunKey
        && pendingReplayResetRunKeyRef.current === options.replayRunKey
        && event.type !== "free_debate_clock"
      ) {
        pendingReplayResetRunKeyRef.current = null;
        setJudgeAnalysisStream("");
        setRoomSession((current) => {
          const resumed = resolveResumableStreamingTurn(current);
          if (resumed.turnId == null) {
            return current;
          }

          return {
            ...current,
            turns: current.turns.map((turn) =>
              turn.id === resumed.turnId
                ? {
                    ...turn,
                    content: "",
                    reasoning: null,
                  }
                : turn,
            ),
          };
        });
      }

      if (event.type === "error") {
        attachedRunKeyRef.current = null;
        pendingReplayResetRunKeyRef.current = null;
        setActiveStreamingTurnId(null);
        setActiveStreamingTurnStartedAtMs(null);
        setActionError(event.message);
        applySessionStreamEvent(event);
        return;
      }
      if (event.type === "meta" && event.turn.kind === "speaker_turn") {
        setActiveStreamingTurnId(typeof event.turn.id === "number" ? event.turn.id : null);
        setActiveStreamingTurnStartedAtMs(null);
      }
      if (event.type === "speaker_clock") {
        const parsedStartedAt = parseUtcTimestamp(event.started_at);
        if (Number.isFinite(parsedStartedAt)) {
          setActiveStreamingTurnId(event.turn_id);
          setActiveStreamingTurnStartedAtMs(parsedStartedAt);
        }
      }
      if (event.type === "turn_done" || event.type === "done") {
        if (event.type === "done") {
          attachedRunKeyRef.current = null;
          pendingReplayResetRunKeyRef.current = null;
        }
        setActiveStreamingTurnId(null);
        setActiveStreamingTurnStartedAtMs(null);
      }
      if (event.type === "decision_saved") {
        setAiSuggestion(null);
        setJudgeAnalysisStream("");
        onTransientStateChange?.(session.id, null);
      }
      if (event.type === "judge_analysis_token") {
        options?.onJudgeAnalysis?.();
        const runKey =
          (typeof event.run_id === "string" && event.run_id.trim())
            ? event.run_id.trim()
            : options?.replayRunKey
          ?? debateActiveRunKey(latestRoomSessionRef.current.id, latestRoomSessionRef.current.active_run);
        const lastSeq = eventSeq;
        setJudgeAnalysisStream((current) => {
          const next = current + event.content;
          onTransientStateChange?.(session.id, { judgeAnalysisStream: next, runKey, lastSeq });
          return next;
        });
        return;
      }
      if (event.type === "ai_suggestion") {
        options?.onJudgeSuggestion?.();
        const suggestion = event.suggestion;
        const runKey =
          (typeof event.run_id === "string" && event.run_id.trim())
            ? event.run_id.trim()
            : options?.replayRunKey
          ?? debateActiveRunKey(latestRoomSessionRef.current.id, latestRoomSessionRef.current.active_run);
        const lastSeq = eventSeq;
        setAiSuggestion(suggestion);
        onTransientStateChange?.(session.id, {
          aiSuggestion: suggestion,
          runKey,
          lastSeq,
          ...(suggestionAnalysisMarkdown(suggestion) ? { judgeAnalysisStream: "" } : {}),
        });
        if (suggestionAnalysisMarkdown(suggestion)) {
          setJudgeAnalysisStream("");
        }
        setWinner(
          toDecisionWinner(
            normalizeWinnerSide(suggestion.winner as DebateWinner, {
              pro_score: suggestion.pro_score,
              con_score: suggestion.con_score,
            }),
          ),
        );
        if (suggestion.pro_score != null) {
          setProScore(String(suggestion.pro_score));
        }
        if (suggestion.con_score != null) {
          setConScore(String(suggestion.con_score));
        }
        if (suggestion.judge_comment) {
          setJudgeComment(suggestion.judge_comment);
        }
        return;
      }

      applySessionStreamEvent(event);
    },
    [applySessionStreamEvent, onTransientStateChange, session.id, syncActiveRunProgress, transientState?.lastSeq, transientState?.runKey],
  );

  useEffect(() => {
    const activeRun = roomSession.active_run;
    if (!activeRun || runningActionRef.current !== null) {
      return;
    }

    const runKey = debateActiveRunKey(roomSession.id, activeRun);
    if (!runKey) {
      return;
    }
    if (attachedRunKeyRef.current === runKey) {
      return;
    }

    const resumeAfterSeq = typeof activeRun.last_seq === "number" && Number.isFinite(activeRun.last_seq)
      ? activeRun.last_seq
      : transientState?.runKey === runKey
        && typeof transientState.lastSeq === "number"
        && Number.isFinite(transientState.lastSeq)
        ? transientState.lastSeq
        : null;

    const { controller, epoch } = beginStreamScope();
    attachedRunKeyRef.current = runKey;
    pendingReplayResetRunKeyRef.current =
      resumeAfterSeq != null && resumeAfterSeq > 0 ? null : runKey;
    updateSidebarRunning(true);

    void streamActiveDebateRun(roomSession.id, {
      onEvent: (event) => {
        if (!isCurrentStreamScope(epoch)) {
          return;
        }
        handleIncomingStreamEvent(event, { replayRunKey: runKey });
      },
      runId: activeRun.run_id ?? null,
      afterSeq: resumeAfterSeq,
      batchWindowMs: 0,
      signal: controller.signal,
    })
      .then(async () => {
        if (controller.signal.aborted || !isCurrentStreamScope(epoch)) {
          return;
        }
        const refreshed = await syncFromServer();
        if (!isCurrentStreamScope(epoch)) {
          return;
        }
        onSessionChange(normalizeRoomSession(refreshed));
      })
      .catch((error) => {
        if (controller.signal.aborted || !isCurrentStreamScope(epoch)) {
          return;
        }
        pendingReplayResetRunKeyRef.current = null;
        if (error instanceof ApiError && (error.status === 404 || error.status === 409)) {
          void syncFromServer().then((refreshed) => {
            if (!isCurrentStreamScope(epoch)) {
              return;
            }
            onSessionChange(normalizeRoomSession(refreshed));
          });
          return;
        }
        const message = error instanceof Error ? error.message : "";
        if (message.includes("No active debate run") || message.includes("404")) {
          void syncFromServer().then((refreshed) => {
            if (!isCurrentStreamScope(epoch)) {
              return;
            }
            onSessionChange(normalizeRoomSession(refreshed));
          });
          return;
        }
        handleStreamError(error, "连接进行中的辩论失败。");
      })
      .finally(() => {
        releaseRequestController(controller);
        if (attachedRunKeyRef.current === runKey) {
          attachedRunKeyRef.current = null;
        }
        if (pendingReplayResetRunKeyRef.current === runKey) {
          pendingReplayResetRunKeyRef.current = null;
        }
        if (!controller.signal.aborted && isCurrentStreamScope(epoch)) {
          updateSidebarRunning(false);
        }
      });

  }, [
    beginStreamScope,
    handleIncomingStreamEvent,
    handleStreamError,
    isCurrentStreamScope,
    onSessionChange,
    releaseRequestController,
    roomSession.active_run,
    roomSession.id,
    syncFromServer,
    transientState?.lastSeq,
    transientState?.runKey,
    updateSidebarRunning,
  ]);

  const handleNextTurn = useCallback(async () => {
    if (!canAdvance) {
      return;
    }

    let receivedJudgeAnalysis = false;
    let receivedJudgeSuggestion = false;
    setActionError(null);
    setJudgeAnalysisStream("");
    const startedAt = markLocalActiveRun("next");
    const runKey = `${roomSession.id}:next:${startedAt}`;
    onTransientStateChange?.(roomSession.id, {
      aiSuggestion: null,
      judgeAnalysisStream: "",
      runKey,
      lastSeq: 0,
    });
    runningActionRef.current = "next";
    setRunningAction("next");
    updateSidebarRunning(true);
    const { controller, epoch } = beginStreamScope();

    try {
      await streamDebateNext(roomSession.id, {
        onEvent: (event) => {
          if (!isCurrentStreamScope(epoch)) {
            return;
          }
          handleIncomingStreamEvent(event, {
            onJudgeAnalysis: () => {
              receivedJudgeAnalysis = true;
            },
            onJudgeSuggestion: () => {
              receivedJudgeSuggestion = true;
            },
          });
        },
        batchWindowMs: 0,
        signal: controller.signal,
      });
      if (!isCurrentStreamScope(epoch)) {
        return;
      }
      if (roomSession.stage === "judge_decision") {
        if (!receivedJudgeAnalysis && !receivedJudgeSuggestion) {
          setActionError("AI 评分没有返回结果。请重试；如果仍无结果，后端可能还在跑旧代码。");
        } else if (receivedJudgeAnalysis && !receivedJudgeSuggestion) {
          setActionError("AI 评分中断，只保留了部分讲评。可再次点击继续评分。");
        }
      }
      const refreshed = await syncFromServer();
      if (!isCurrentStreamScope(epoch)) {
        return;
      }
      onSessionChange(normalizeRoomSession(refreshed));
    } catch (error) {
      if (controller.signal.aborted || !isCurrentStreamScope(epoch)) {
        return;
      }
      setActiveStreamingTurnId(null);
      setActiveStreamingTurnStartedAtMs(null);
      handleStreamError(error, "推进下一回合失败。");
    } finally {
      releaseRequestController(controller);
      if (!isCurrentStreamScope(epoch)) {
        return;
      }
      setActiveStreamingTurnId(null);
      setActiveStreamingTurnStartedAtMs(null);
      runningActionRef.current = null;
      setRunningAction(null);
      if (!controller.signal.aborted) {
        updateSidebarRunning(false);
      }
    }
  }, [
    applySessionStreamEvent,
    beginStreamScope,
    canAdvance,
    handleStreamError,
    handleIncomingStreamEvent,
    isCurrentStreamScope,
    markLocalActiveRun,
    onTransientStateChange,
    onSessionChange,
    releaseRequestController,
    roomSession.id,
    syncFromServer,
    updateSidebarRunning,
  ]);

  const handleAsk = useCallback(async () => {
    const question = askQuestion.trim();
    if (!question || !canAsk) {
      return;
    }

    setActionError(null);
    const startedAt = markLocalActiveRun("ask");
    const runKey = `${roomSession.id}:ask:${startedAt}`;
    onTransientStateChange?.(roomSession.id, {
      aiSuggestion: null,
      judgeAnalysisStream: "",
      runKey,
      lastSeq: 0,
    });
    runningActionRef.current = "ask";
    setRunningAction("ask");
    updateSidebarRunning(true);
    const { controller, epoch } = beginStreamScope();

    try {
      await streamDebateAsk(
        roomSession.id,
        {
          question,
          ask_to: askTarget,
        },
        {
          onEvent: (event) => {
            if (!isCurrentStreamScope(epoch)) {
              return;
            }
            handleIncomingStreamEvent(event);
          },
          batchWindowMs: 0,
          signal: controller.signal,
        },
      );
      if (!isCurrentStreamScope(epoch)) {
        return;
      }
      setAskQuestion("");
      const refreshed = await syncFromServer();
      if (!isCurrentStreamScope(epoch)) {
        return;
      }
      onSessionChange(normalizeRoomSession(refreshed));
    } catch (error) {
      if (controller.signal.aborted || !isCurrentStreamScope(epoch)) {
        return;
      }
      setActiveStreamingTurnId(null);
      setActiveStreamingTurnStartedAtMs(null);
      handleStreamError(error, "裁判追问失败。");
    } finally {
      releaseRequestController(controller);
      if (!isCurrentStreamScope(epoch)) {
        return;
      }
      setActiveStreamingTurnId(null);
      setActiveStreamingTurnStartedAtMs(null);
      runningActionRef.current = null;
      setRunningAction(null);
      if (!controller.signal.aborted) {
        updateSidebarRunning(false);
      }
    }
  }, [
    applySessionStreamEvent,
    askQuestion,
    askTarget,
    beginStreamScope,
    canAsk,
    handleStreamError,
    handleIncomingStreamEvent,
    isCurrentStreamScope,
    markLocalActiveRun,
    onSessionChange,
    releaseRequestController,
    roomSession.id,
    syncFromServer,
    updateSidebarRunning,
  ]);

  const handleDecision = useCallback(async () => {
    if (runningAction !== null) {
      return;
    }

    setActionError(null);
    const startedAt = markLocalActiveRun("decision");
    const runKey = `${roomSession.id}:decision:${startedAt}`;
    onTransientStateChange?.(roomSession.id, {
      aiSuggestion: null,
      judgeAnalysisStream: "",
      runKey,
      lastSeq: 0,
    });
    runningActionRef.current = "decision";
    setRunningAction("decision");
    updateSidebarRunning(true);
    const { controller, epoch } = beginStreamScope();

    try {
      await streamDebateDecision(
        roomSession.id,
        {
          winner_side: winner,
          judge_comment: judgeComment.trim(),
          scoring_json: buildDecisionScoringJson(
            (aiSuggestion?.scoring_json as Record<string, unknown> | undefined) ??
              roomSession.judge_decision?.scoring_json,
            proScore,
            conScore,
          ),
        },
        {
          onEvent: (event) => {
            if (!isCurrentStreamScope(epoch)) {
              return;
            }
            handleIncomingStreamEvent(event);
          },
          batchWindowMs: 0,
          signal: controller.signal,
        },
      );

      if (!isCurrentStreamScope(epoch)) {
        return;
      }
      const refreshed = await syncFromServer();
      if (!isCurrentStreamScope(epoch)) {
        return;
      }
      onSessionChange(normalizeRoomSession(refreshed));
    } catch (error) {
      if (controller.signal.aborted || !isCurrentStreamScope(epoch)) {
        return;
      }
      setActiveStreamingTurnId(null);
      setActiveStreamingTurnStartedAtMs(null);
      handleStreamError(error, "提交裁决失败。");
    } finally {
      releaseRequestController(controller);
      if (!isCurrentStreamScope(epoch)) {
        return;
      }
      setActiveStreamingTurnId(null);
      setActiveStreamingTurnStartedAtMs(null);
      runningActionRef.current = null;
      setRunningAction(null);
      if (!controller.signal.aborted) {
        updateSidebarRunning(false);
      }
    }
  }, [
    conScore,
    beginStreamScope,
    handleStreamError,
    handleIncomingStreamEvent,
    isCurrentStreamScope,
    judgeComment,
    markLocalActiveRun,
    onSessionChange,
    applySessionStreamEvent,
    onTransientStateChange,
    proScore,
    releaseRequestController,
    roomSession.id,
    runningAction,
    syncFromServer,
    updateSidebarRunning,
    winner,
  ]);

  const participantWinner = roomSession.judge_decision
    ? normalizeWinnerSide(roomSession.judge_decision.winner_side, roomSession.judge_decision.scoring_json)
    : null;
  const showOutcomeBanner = roomSession.stage === "judge_decision" && participantWinner !== null;
  const showStageHeader = showStageTimer || showOutcomeBanner;
  const activeTimedSide =
    locallyFinalizingTurnId == null && activeTimedTurn?.speaker_participant_id != null
      ? (participantMap.get(activeTimedTurn.speaker_participant_id)?.side ?? null)
      : null;
  const activeTimedCountingSide =
    activeStreamingTurnStartedAtMs != null ? activeTimedSide : null;
  const freeDebateActiveSide =
    freeDebateExpiredTurnId == null ? freeDebateState?.active_side ?? null : null;
  const freeDebateCountingSide =
    freeDebateState?.active_turn_started_at ? freeDebateActiveSide : null;
  const judgeScoringSource =
    (aiSuggestion?.scoring_json as Record<string, unknown> | undefined) ??
    roomSession.judge_decision?.scoring_json;
  const stageScores = extractStageScores(judgeScoringSource);
  const judgeAnalysis = extractJudgeAnalysis(judgeScoringSource);
  const persistedJudgeAnalysisMarkdown = extractJudgeAnalysisMarkdown(judgeScoringSource);
  const hasResolvedJudgeResult = !!aiSuggestion || roomSession.judge_decision !== null;
  const hasIncompleteJudgeResult = judgeAnalysisStream.trim().length > 0 && !hasResolvedJudgeResult;
  const judgeEvaluationRunning =
    runningAction === "next" || roomSession.active_run?.action === "next";
  const judgeCardPending =
    roomSession.stage === "judge_decision"
    && !hasResolvedJudgeResult
    && judgeEvaluationRunning;
  const judgeAnalysisMarkdown =
    persistedJudgeAnalysisMarkdown || judgeAnalysisStream;
  const judgeCardComment =
    aiSuggestion?.judge_comment ?? roomSession.judge_decision?.judge_comment ?? "";
  const judgeCardWinner =
    (aiSuggestion
      ? normalizeWinnerSide(aiSuggestion.winner as DebateWinner, {
          pro_score: aiSuggestion.pro_score,
          con_score: aiSuggestion.con_score,
        })
      : participantWinner) ?? null;
  const nextTurnLabel =
    roomSession.stage === "judge_decision"
      ? hasResolvedJudgeResult
        ? "重新评分"
        : hasIncompleteJudgeResult
          ? "继续评分"
          : "请 AI 评分"
      : roomSession.stage === "free_debate"
        ? (freeDebateState?.turn_count ?? 0) > 0
          ? "继续自由辩论"
          : "开始自由辩论"
        : !hasTurns
          ? "开始第一回合"
          : "下一回合";
  const nextTurnRunningLabel =
    roomSession.stage === "judge_decision"
      ? "AI 正在评分…"
      : roomSession.stage === "free_debate"
        ? "自由辩论进行中…"
        : "正在生成…";
  const stageTimerTitle = showOutcomeBanner
    ? `${WINNER_LABEL[participantWinner ?? "pro"]}获胜`
    : roomSession.stage === "free_debate"
      ? "自由辩论"
      : STAGE_LABEL[roomSession.stage];

  useEffect(() => {
    if (judgeAnalysisStream || judgeAnalysisMarkdown || judgeCardComment || stageScores.length > 0) {
      setJudgeExpanded(true);
    }
  }, [judgeAnalysisStream, judgeAnalysisMarkdown, judgeCardComment, stageScores.length]);

  useEffect(() => {
    if (pendingScrollToBottomSessionRef.current !== session.id) {
      return;
    }

    const scrollContainer = scrollRef.current;
    if (!scrollContainer) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      scrollContainer.scrollTop = scrollContainer.scrollHeight;
      pendingScrollToBottomSessionRef.current = null;
    });

    return () => window.cancelAnimationFrame(frame);
  }, [judgeAnalysisStream, roomSession.summary, session.id, sortedTurns]);

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto" ref={scrollRef}>
        <div className="flex min-h-full w-full flex-col">
          <div className="flex min-h-full flex-1 overflow-hidden border-t border-app-border bg-app-panel">
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="border-b border-app-border px-6 py-5 md:px-7">
                <div className="text-[28px] font-semibold tracking-[-0.05em] text-app-text">
                  {roomSession.topic}
                </div>
              </div>

              <div className="border-bottom border-app-border">
                <DebateStageHeader
                  conActive={
                    roomSession.stage === "free_debate"
                      ? freeDebateActiveSide === "con"
                      : activeTimedSide === "con"
                  }
                  conCounting={
                    roomSession.stage === "free_debate"
                      ? freeDebateCountingSide === "con"
                      : activeTimedCountingSide === "con"
                  }
                  conModelLabel={conModelLabel}
                  conRemainingMs={conRemainingMs}
                  participantWinner={participantWinner}
                  proActive={
                    roomSession.stage === "free_debate"
                      ? freeDebateActiveSide === "pro"
                      : activeTimedSide === "pro"
                  }
                  proCounting={
                    roomSession.stage === "free_debate"
                      ? freeDebateCountingSide === "pro"
                      : activeTimedCountingSide === "pro"
                  }
                  proModelLabel={proModelLabel}
                  proRemainingMs={proRemainingMs}
                  showStageHeader={showStageHeader}
                  showStageTimer={showStageTimer}
                  stageTimerTitle={stageTimerTitle}
                />

                {hasTurns ? (
                  <div className="border-b border-app-border px-6 py-4 md:px-7">
                    <div className="grid grid-cols-5 items-center gap-2 md:flex md:justify-between md:gap-8">
                      {FLOW_STEPS.map((step, index) => {
                        const isActive = step.stage === roomSession.stage;
                        const isDone = currentStepIndex > index;
                        return (
                          <div
                            className="flex min-w-0 items-center justify-center gap-1.5 md:min-w-[112px] md:gap-2.5"
                            key={step.stage}
                          >
                            <span
                              className={`h-2.5 w-2.5 rounded-full ${
                                isActive
                                  ? "bg-[#2f8f57]"
                                  : isDone
                                    ? "bg-app-text/60"
                                    : "bg-app-border"
                              }`}
                            />
                            <span
                              className={`truncate whitespace-nowrap text-[13px] md:text-[14px] ${
                                isActive
                                  ? "font-semibold text-[#2f8f57]"
                                  : isDone
                                    ? "text-app-text/80"
                                    : "text-app-muted"
                              }`}
                            >
                              {step.label}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="flex min-h-0 flex-1 flex-col">
                <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto">
                  {!hasTurns ? (
                    <div className="min-h-[240px] md:min-h-[320px]" />
                  ) : (
                    <>
                      {sortedTurns.map((turn) => {
                        const participant =
                          turn.speaker_participant_id != null
                            ? participantMap.get(turn.speaker_participant_id) ?? null
                            : null;

                        return (
                          <DebateTurnCard
                            isFinalizingTimeout={locallyFinalizingTurnId === turn.id}
                            isStreaming={activeStreamingTurnId === turn.id && locallyFinalizingTurnId !== turn.id}
                            key={`${turn.id}`}
                            participant={participant}
                            sequenceNumber={freeDebateSequenceByTurnId.get(turn.id) ?? null}
                            turn={turn}
                          />
                        );
                      })}
                      <DebateJudgeCard
                        analysis={judgeAnalysis}
                        analysisMarkdown={judgeAnalysisMarkdown}
                        expanded={judgeExpanded}
                        judgeComment={judgeCardComment}
                        onToggle={() => setJudgeExpanded((current) => !current)}
                        partial={hasIncompleteJudgeResult && !judgeCardPending}
                        pending={judgeCardPending}
                        stageScores={stageScores}
                        winner={judgeCardWinner}
                      />
                    </>
                  )}
                </div>

                <DebateControls
                  actionError={actionError}
                  askQuestion={askQuestion}
                  askTarget={askTarget}
                  canAdvance={canAdvance}
                  canAsk={canAsk}
                  conScore={conScore}
                  judgeComment={judgeComment}
                  nextTurnLabel={nextTurnLabel}
                  nextTurnRunningLabel={nextTurnRunningLabel}
                  onAsk={() => void handleAsk()}
                  onAskQuestionChange={setAskQuestion}
                  onAskTargetChange={setAskTarget}
                  onConScoreChange={setConScore}
                  onDecision={() => void handleDecision()}
                  onJudgeCommentChange={setJudgeComment}
                  onNextTurn={() => void handleNextTurn()}
                  onProScoreChange={setProScore}
                  onToggleWinner={() => setWinner((current) => (current === "pro" ? "con" : "pro"))}
                  proScore={proScore}
                  runningAction={runningAction}
                  stage={roomSession.stage}
                  status={roomSession.status}
                  winner={winner}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
