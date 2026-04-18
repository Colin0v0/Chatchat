import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { streamDebateAsk, streamDebateDecision, streamDebateNext } from "../../../lib/api";
import type {
  DebateAiSuggestion,
  DebateAskTarget,
  DebateSessionDetail,
  DebateStage,
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

export function DebateRoomView({
  session,
  onRefresh,
  onSessionChange,
}: {
  session: DebateSessionDetail;
  onRefresh: (sessionId: number) => Promise<DebateSessionDetail>;
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
  const [aiSuggestion, setAiSuggestion] = useState<DebateAiSuggestion | null>(null);
  const [activeStreamingTurnId, setActiveStreamingTurnId] = useState<number | null>(null);
  const [activeStreamingTurnStartedAtMs, setActiveStreamingTurnStartedAtMs] = useState<number | null>(null);
  const [freeDebateClockAnchor, setFreeDebateClockAnchor] = useState<{
    turnId: number | null;
    startedAtMs: number | null;
  }>(() => ({
    turnId: session.free_debate_state?.active_turn_id ?? null,
    startedAtMs: resolveFreeDebateClockAnchorMs(session.free_debate_state),
  }));
  const [clockNow, setClockNow] = useState(() => Date.now());
  const [judgeExpanded, setJudgeExpanded] = useState(true);
  const [judgeAnalysisStream, setJudgeAnalysisStream] = useState("");

  useEffect(() => {
    if (runningActionRef.current !== null) {
      return;
    }

    const normalizedSession = normalizeRoomSession(session);
    const isSameSession = lastSessionIdRef.current === session.id;
    lastSessionIdRef.current = session.id;

    setRoomSession(normalizedSession);
    setActiveStreamingTurnId(null);
    setActiveStreamingTurnStartedAtMs(null);
    setFreeDebateClockAnchor({
      turnId: normalizedSession.free_debate_state?.active_turn_id ?? null,
      startedAtMs: resolveFreeDebateClockAnchorMs(normalizedSession.free_debate_state),
    });
    setJudgeAnalysisStream(
      extractJudgeAnalysisMarkdown(normalizedSession.judge_decision?.scoring_json as Record<string, unknown> | undefined),
    );

    if (normalizedSession.judge_decision) {
      setAiSuggestion(null);
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

    setAiSuggestion(null);
    setWinner("pro");
    setJudgeComment("");
    setProScore("");
    setConScore("");
  }, [session]);

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

  const canAdvance =
    runningAction === null &&
    roomSession.status !== "finished" &&
    (roomSession.stage !== "judge_decision" || roomSession.judge_decision === null);
  const canAsk = runningAction === null && roomSession.status !== "finished";
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
      stageBudgetMs(roomSession, activeTimedTurn.stage) > 0;

    if (!hasFreeDebateTicker && !hasStageTicker) {
      return;
    }

    setClockNow(Date.now());
    const timerId = window.setInterval(() => setClockNow(Date.now()), 100);
    return () => window.clearInterval(timerId);
  }, [
    activeTimedTurn,
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

  const syncFromServer = useCallback(async () => {
    const refreshed = await onRefresh(roomSession.id);
    setRoomSession(normalizeRoomSession(refreshed));
    return refreshed;
  }, [onRefresh, roomSession.id]);

  const handleStreamError = useCallback((error: unknown, fallback: string) => {
    setActionError(error instanceof Error ? error.message : fallback);
  }, []);

  const handleNextTurn = useCallback(async () => {
    if (!canAdvance) {
      return;
    }

    setActionError(null);
    setJudgeAnalysisStream("");
    runningActionRef.current = "next";
    setRunningAction("next");

    try {
      await streamDebateNext(roomSession.id, {
        onEvent: (event) => {
          if (event.type === "error") {
            setActiveStreamingTurnId(null);
            setActionError(event.message);
            return;
          }
          if (event.type === "meta" && event.turn.kind === "speaker_turn") {
            setActiveStreamingTurnId(typeof event.turn.id === "number" ? event.turn.id : null);
            setActiveStreamingTurnStartedAtMs(Date.now());
          }
          if (event.type === "turn_done" || event.type === "done") {
            setActiveStreamingTurnId(null);
            setActiveStreamingTurnStartedAtMs(null);
          }
          if (event.type === "judge_analysis_token") {
            setJudgeAnalysisStream((current) => current + event.content);
            return;
          }
          if (event.type === "ai_suggestion") {
            const suggestion = event.suggestion;
            setAiSuggestion(suggestion);
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

          setRoomSession((current) => applyStreamEvent(current, event));
        },
      });
      await syncFromServer();
    } catch (error) {
      setActiveStreamingTurnId(null);
      setActiveStreamingTurnStartedAtMs(null);
      handleStreamError(error, "推进下一回合失败。");
    } finally {
      setActiveStreamingTurnId(null);
      setActiveStreamingTurnStartedAtMs(null);
      runningActionRef.current = null;
      setRunningAction(null);
    }
  }, [canAdvance, handleStreamError, roomSession.id, syncFromServer]);

  const handleAsk = useCallback(async () => {
    const question = askQuestion.trim();
    if (!question || !canAsk) {
      return;
    }

    setActionError(null);
    runningActionRef.current = "ask";
    setRunningAction("ask");

    try {
      await streamDebateAsk(
        roomSession.id,
        {
          question,
          ask_to: askTarget,
        },
        {
          onEvent: (event) => {
          if (event.type === "error") {
            setActiveStreamingTurnId(null);
            setActionError(event.message);
            return;
          }
          if (event.type === "meta" && event.turn.kind === "speaker_turn") {
            setActiveStreamingTurnId(typeof event.turn.id === "number" ? event.turn.id : null);
            setActiveStreamingTurnStartedAtMs(Date.now());
          }
            if (event.type === "turn_done" || event.type === "done") {
              setActiveStreamingTurnId(null);
              setActiveStreamingTurnStartedAtMs(null);
            }
            setRoomSession((current) => applyStreamEvent(current, event));
          },
        },
      );
      setAskQuestion("");
      await syncFromServer();
    } catch (error) {
      setActiveStreamingTurnId(null);
      setActiveStreamingTurnStartedAtMs(null);
      handleStreamError(error, "裁判追问失败。");
    } finally {
      setActiveStreamingTurnId(null);
      setActiveStreamingTurnStartedAtMs(null);
      runningActionRef.current = null;
      setRunningAction(null);
    }
  }, [askQuestion, askTarget, canAsk, handleStreamError, roomSession.id, syncFromServer]);

  const handleDecision = useCallback(async () => {
    if (runningAction !== null) {
      return;
    }

    setActionError(null);
    setJudgeAnalysisStream("");
    setAiSuggestion(null);
    runningActionRef.current = "decision";
    setRunningAction("decision");

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
            if (event.type === "error") {
              setActiveStreamingTurnId(null);
              setActionError(event.message);
              return;
            }
            if (event.type === "done") {
              setActiveStreamingTurnId(null);
              setActiveStreamingTurnStartedAtMs(null);
            }
            if (event.type === "judge_analysis_token") {
              setJudgeAnalysisStream((current) => current + event.content);
              return;
            }
            if (event.type === "ai_suggestion") {
              const suggestion = event.suggestion;
              setAiSuggestion(suggestion);
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

            setRoomSession((current) => applyStreamEvent(current, event));
          },
        },
      );

      const refreshed = await syncFromServer();
      onSessionChange(normalizeRoomSession(refreshed));
    } catch (error) {
      setActiveStreamingTurnId(null);
      setActiveStreamingTurnStartedAtMs(null);
      handleStreamError(error, "提交裁决失败。");
    } finally {
      setActiveStreamingTurnId(null);
      setActiveStreamingTurnStartedAtMs(null);
      runningActionRef.current = null;
      setRunningAction(null);
    }
  }, [
    conScore,
    handleStreamError,
    judgeComment,
    onSessionChange,
    proScore,
    roomSession.id,
    runningAction,
    syncFromServer,
    winner,
  ]);

  const participantWinner = roomSession.judge_decision
    ? normalizeWinnerSide(roomSession.judge_decision.winner_side, roomSession.judge_decision.scoring_json)
    : null;
  const showOutcomeBanner = roomSession.stage === "judge_decision" && participantWinner !== null;
  const showStageHeader = showStageTimer || showOutcomeBanner;
  const activeTimedSide =
    activeTimedTurn?.speaker_participant_id != null
      ? (participantMap.get(activeTimedTurn.speaker_participant_id)?.side ?? null)
      : null;
  const nextTurnLabel =
    roomSession.stage === "judge_decision"
      ? aiSuggestion
        ? "重新评分"
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
  const judgeScoringSource =
    (aiSuggestion?.scoring_json as Record<string, unknown> | undefined) ??
    roomSession.judge_decision?.scoring_json;
  const stageScores = extractStageScores(judgeScoringSource);
  const judgeAnalysis = extractJudgeAnalysis(judgeScoringSource);
  const judgeAnalysisMarkdown =
    judgeAnalysisStream || extractJudgeAnalysisMarkdown(judgeScoringSource);
  const judgeCardComment =
    aiSuggestion?.judge_comment ?? roomSession.judge_decision?.judge_comment ?? "";
  const judgeCardWinner =
    (aiSuggestion
      ? normalizeWinnerSide(aiSuggestion.winner as DebateWinner, {
          pro_score: aiSuggestion.pro_score,
          con_score: aiSuggestion.con_score,
        })
      : participantWinner) ?? null;

  useEffect(() => {
    if (judgeAnalysisStream || judgeAnalysisMarkdown || judgeCardComment || stageScores.length > 0) {
      setJudgeExpanded(true);
    }
  }, [judgeAnalysisStream, judgeAnalysisMarkdown, judgeCardComment, stageScores.length]);

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto">
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
                      ? freeDebateState?.active_side === "con"
                      : activeTimedSide === "con"
                  }
                  conModelLabel={conModelLabel}
                  conRemainingMs={displayedRemainingMs("con")}
                  participantWinner={participantWinner}
                  proActive={
                    roomSession.stage === "free_debate"
                      ? freeDebateState?.active_side === "pro"
                      : activeTimedSide === "pro"
                  }
                  proModelLabel={proModelLabel}
                  proRemainingMs={displayedRemainingMs("pro")}
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
                            isStreaming={activeStreamingTurnId === turn.id}
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
