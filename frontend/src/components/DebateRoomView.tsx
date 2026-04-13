import {
  ChevronLeft,
  LoaderCircle,
  MessageSquareQuote,
  Play,
  Scale,
  Sparkles,
  Trophy,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { streamDebateAsk, streamDebateNext, submitDebateDecision } from "../lib/api";
import type {
  DebateAskTarget,
  DebateParticipant,
  DebateSessionDetail,
  DebateStreamEvent,
  DebateTurn,
  DebateWinner,
} from "../types";

const STAGE_LABEL: Record<DebateTurn["stage"], string> = {
  opening: "立论",
  rebuttal: "驳论",
  closing: "总结",
  judge_decision: "裁判阶段",
};

const STATUS_LABEL: Record<DebateSessionDetail["status"], string> = {
  created: "未开始",
  running: "进行中",
  waiting_judge: "等待裁决",
  finished: "已结束",
};

const WINNER_LABEL: Record<DebateWinner, string> = {
  pro: "正方",
  con: "反方",
  draw: "平局",
};

const FLOW_STEPS: Array<{ stage: DebateSessionDetail["stage"]; label: string }> = [
  { stage: "opening", label: "立论" },
  { stage: "rebuttal", label: "驳论" },
  { stage: "closing", label: "总结" },
  { stage: "judge_decision", label: "裁决" },
];

function normalizeRoomSession(session: DebateSessionDetail): DebateSessionDetail {
  return {
    ...session,
    participants: Array.isArray(session.participants) ? session.participants : [],
    turns: Array.isArray(session.turns) ? session.turns : [],
    judge_decision: session.judge_decision ?? null,
    summary: typeof session.summary === "string" ? session.summary : "",
  };
}

function SideBadge({ side }: { side: DebateParticipant["side"] }) {
  const label = side === "pro" ? "正方" : "反方";
  const className =
    side === "pro"
      ? "bg-app-accent-soft text-app-accent-strong"
      : "bg-[#f7ebe8] text-[#9d3d32]";

  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-[12px] font-semibold ${className}`}>
      {label}
    </span>
  );
}

function StageBadge({ stage }: { stage: DebateTurn["stage"] | DebateSessionDetail["stage"] }) {
  return (
    <span className="inline-flex rounded-full bg-app-panel-strong px-2.5 py-1 text-[12px] font-semibold text-app-muted">
      {STAGE_LABEL[stage]}
    </span>
  );
}

function upsertTurn(turns: DebateTurn[], nextTurn: DebateTurn) {
  const existingIndex = turns.findIndex((turn) => turn.id === nextTurn.id);
  if (existingIndex === -1) {
    return [...turns, nextTurn].sort((left, right) => left.turn_index - right.turn_index);
  }

  return turns.map((turn, index) => (index === existingIndex ? nextTurn : turn));
}

function patchTurn(
  turns: DebateTurn[],
  turnId: number,
  patch: (turn: DebateTurn) => DebateTurn,
) {
  return turns.map((turn) => (turn.id === turnId ? patch(turn) : turn));
}

function applyStreamEvent(session: DebateSessionDetail, event: DebateStreamEvent): DebateSessionDetail {
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
    case "done":
      return {
        ...normalizedSession,
        stage: event.stage,
        status: event.status,
      };
    case "error":
      return normalizedSession;
  }
}

function scoreValue(score: unknown) {
  return typeof score === "number" && Number.isFinite(score) ? String(score) : "";
}

export function DebateRoomView({
  session,
  onBack,
  onRefresh,
  onSessionChange,
}: {
  session: DebateSessionDetail;
  onBack: () => void;
  onRefresh: (sessionId: number) => Promise<DebateSessionDetail>;
  onSessionChange: (session: DebateSessionDetail) => void;
}) {
  const [roomSession, setRoomSession] = useState(() => normalizeRoomSession(session));
  const [askTarget, setAskTarget] = useState<DebateAskTarget>("all");
  const [askQuestion, setAskQuestion] = useState("");
  const [winner, setWinner] = useState<DebateWinner>(session.judge_decision?.winner_side ?? "pro");
  const [judgeComment, setJudgeComment] = useState(session.judge_decision?.judge_comment ?? "");
  const [proScore, setProScore] = useState(scoreValue(session.judge_decision?.scoring_json?.pro_score));
  const [conScore, setConScore] = useState(scoreValue(session.judge_decision?.scoring_json?.con_score));
  const [runningAction, setRunningAction] = useState<"next" | "ask" | "decision" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    setRoomSession(normalizeRoomSession(session));
    setWinner(session.judge_decision?.winner_side ?? "pro");
    setJudgeComment(session.judge_decision?.judge_comment ?? "");
    setProScore(scoreValue(session.judge_decision?.scoring_json?.pro_score));
    setConScore(scoreValue(session.judge_decision?.scoring_json?.con_score));
  }, [session]);

  const participantMap = useMemo(
    () => new Map(roomSession.participants.map((participant) => [participant.id, participant])),
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

  const canAdvance =
    runningAction === null && roomSession.stage !== "judge_decision" && roomSession.status !== "finished";
  const canAsk = runningAction === null && roomSession.status !== "finished";
  const currentStepIndex = FLOW_STEPS.findIndex((step) => step.stage === roomSession.stage);

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
    setRunningAction("next");
    try {
      await streamDebateNext(roomSession.id, {
        onEvent: (event) => {
          if (event.type === "error") {
            setActionError(event.message);
            return;
          }
          setRoomSession((current) => applyStreamEvent(current, event));
        },
      });
      await syncFromServer();
    } catch (error) {
      handleStreamError(error, "推进下一回合失败。");
    } finally {
      setRunningAction(null);
    }
  }, [canAdvance, handleStreamError, roomSession.id, syncFromServer]);

  const handleAsk = useCallback(async () => {
    const question = askQuestion.trim();
    if (!question || !canAsk) {
      return;
    }

    setActionError(null);
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
              setActionError(event.message);
              return;
            }
            setRoomSession((current) => applyStreamEvent(current, event));
          },
        },
      );
      setAskQuestion("");
      await syncFromServer();
    } catch (error) {
      handleStreamError(error, "裁判追问失败。");
    } finally {
      setRunningAction(null);
    }
  }, [askQuestion, askTarget, canAsk, handleStreamError, roomSession.id, syncFromServer]);

  const handleDecision = useCallback(async () => {
    if (runningAction !== null) {
      return;
    }

    setActionError(null);
    setRunningAction("decision");
    try {
      const nextSession = await submitDebateDecision(roomSession.id, {
        winner_side: winner,
        judge_comment: judgeComment.trim(),
        scoring_json: {
          ...(proScore.trim() ? { pro_score: Number(proScore) } : {}),
          ...(conScore.trim() ? { con_score: Number(conScore) } : {}),
        },
      });
      const normalized = normalizeRoomSession(nextSession);
      setRoomSession(normalized);
      onSessionChange(normalized);
    } catch (error) {
      handleStreamError(error, "提交裁决失败。");
    } finally {
      setRunningAction(null);
    }
  }, [conScore, handleStreamError, judgeComment, onSessionChange, proScore, roomSession.id, runningAction, winner]);

  return (
    <section className="flex min-h-0 flex-1 flex-col pb-1">
      <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto pt-3">
        <div className="mx-auto flex w-full max-w-[1260px] flex-col px-4 md:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3 px-1 pb-3">
            <button
              className="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
              onClick={onBack}
              type="button"
            >
              <ChevronLeft className="size-4" />
              返回主页
            </button>

            <div className="flex items-center gap-3 text-[13px] font-medium text-app-muted">
              <span>{STAGE_LABEL[roomSession.stage]}</span>
              <span className="h-1 w-1 rounded-full bg-app-border" />
              <span>{STATUS_LABEL[roomSession.status]}</span>
            </div>
          </div>

          <div className="flex min-h-0 flex-1 overflow-hidden rounded-[30px] border border-app-border bg-app-panel shadow-[0_24px_80px_rgba(34,24,16,0.08)]">
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="border-b border-app-border px-6 py-5 md:px-7">
                <div className="flex flex-wrap items-start justify-between gap-5">
                  <div className="min-w-0">
                    <div className="flex items-center gap-3">
                      <div className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-app-panel-strong text-app-muted">
                        <Scale className="size-4" />
                      </div>
                      <div className="text-[12px] font-semibold tracking-[0.18em] text-app-muted uppercase">
                        Debate
                      </div>
                    </div>
                    <div className="mt-3 text-[28px] font-semibold tracking-[-0.05em] text-app-text">
                      {roomSession.topic}
                    </div>
                    <div className="mt-2 max-w-[760px] text-[14px] leading-7 text-app-muted">
                      左边只看立场和流程，中间连续看攻防记录，右边集中控场操作；整个页面只保留一个整体容器。
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <StageBadge stage={roomSession.stage} />
                    <span className="inline-flex rounded-full bg-app-accent-soft px-2.5 py-1 text-[12px] font-semibold text-app-accent-strong">
                      {STATUS_LABEL[roomSession.status]}
                    </span>
                  </div>
                </div>
              </div>

              <div className="grid min-h-0 flex-1 grid-cols-1 xl:grid-cols-[230px_minmax(0,1fr)_320px]">
                <aside className="border-b border-app-border bg-app-panel-soft/35 xl:border-r xl:border-b-0">
                  <div className="border-b border-app-border px-6 py-4 text-[12px] font-semibold tracking-[0.16em] text-app-muted uppercase">
                    阵营与流程
                  </div>

                  <div className="px-6 py-4">
                    <div className="space-y-4">
                      {roomSession.participants.map((participant) => (
                        <div
                          className={`border-l-2 pl-4 ${
                            participant.side === "pro" ? "border-app-accent-strong" : "border-[#c77467]"
                          }`}
                          key={participant.id}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0 text-[14px] font-semibold text-app-text">
                              <div className="truncate">{participant.model_id}</div>
                              <div className="mt-1 text-[12px] font-medium text-app-muted">
                                发言顺序 {participant.order_index + 1}
                              </div>
                            </div>
                            <SideBadge side={participant.side} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="border-t border-app-border px-6 py-4">
                    <div className="text-[12px] font-semibold tracking-[0.16em] text-app-muted uppercase">
                      当前流程
                    </div>
                    <div className="mt-4 space-y-3">
                      {FLOW_STEPS.map((step, index) => {
                        const isActive = step.stage === roomSession.stage;
                        const isDone = currentStepIndex > index;
                        return (
                          <div className="flex items-center gap-3" key={step.stage}>
                            <span
                              className={`h-2.5 w-2.5 rounded-full ${
                                isActive
                                  ? "bg-app-accent-strong"
                                  : isDone
                                    ? "bg-app-text/60"
                                    : "bg-app-border"
                              }`}
                            />
                            <span
                              className={`text-[14px] ${
                                isActive
                                  ? "font-semibold text-app-text"
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
                </aside>

                <main className="flex min-h-0 flex-col border-b border-app-border xl:border-r xl:border-b-0">
                  <div className="flex items-center justify-between gap-3 border-b border-app-border px-6 py-4">
                    <div>
                      <div className="text-[18px] font-semibold tracking-[-0.03em] text-app-text">辩论记录</div>
                      <div className="mt-1 text-[13px] text-app-muted">
                        共 {sortedTurns.length} 条记录，所有攻防都在这里连续展开。
                      </div>
                    </div>
                    {runningAction ? (
                      <div className="inline-flex items-center gap-2 text-[13px] text-app-muted">
                        <LoaderCircle className="size-3.5 animate-spin" />
                        {runningAction === "next"
                          ? "正在生成回合..."
                          : runningAction === "ask"
                            ? "正在处理追问..."
                            : "正在提交裁决..."}
                      </div>
                    ) : null}
                  </div>

                  <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto">
                    {sortedTurns.length === 0 ? (
                      <div className="flex h-full flex-col items-center justify-center px-8 py-16 text-center">
                        <div className="text-[20px] font-semibold tracking-[-0.03em] text-app-text">
                          还没有发言记录
                        </div>
                        <div className="mt-2 max-w-[420px] text-[14px] leading-7 text-app-muted">
                          从这里开始整场辩论。点一次“下一回合”，正方会先开始立论，后续记录会连续铺开。
                        </div>
                        <button
                          className="mt-6 inline-flex items-center gap-2 rounded-2xl bg-app-accent-soft px-5 py-3 text-[15px] font-semibold text-app-accent-strong transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-60"
                          disabled={!canAdvance}
                          onClick={() => void handleNextTurn()}
                          type="button"
                        >
                          <Play className="size-4" />
                          开始第一回合
                        </button>
                      </div>
                    ) : (
                      sortedTurns.map((turn) => {
                        const participant =
                          turn.speaker_participant_id != null
                            ? participantMap.get(turn.speaker_participant_id) ?? null
                            : null;

                        return (
                          <article
                            className="grid grid-cols-1 gap-3 border-b border-app-border px-6 py-5 md:grid-cols-[136px_minmax(0,1fr)]"
                            key={`${turn.id}`}
                          >
                            <div className="min-w-0">
                              {turn.kind === "judge_question" ? (
                                <>
                                  <div className="text-[13px] font-semibold text-app-text">裁判追问</div>
                                  <div className="mt-1 text-[12px] text-app-muted">{STAGE_LABEL[turn.stage]}</div>
                                </>
                              ) : (
                                <>
                                  <div className="truncate text-[13px] font-semibold text-app-text">
                                    {participant?.model_id ?? "辩手"}
                                  </div>
                                  <div className="mt-2 flex flex-wrap items-center gap-2">
                                    {participant ? <SideBadge side={participant.side} /> : null}
                                    <StageBadge stage={turn.stage} />
                                  </div>
                                </>
                              )}
                            </div>

                            <div className="min-w-0">
                              <div className="whitespace-pre-wrap text-[15px] leading-8 text-app-text">
                                {turn.content || (
                                  <span className="text-app-muted">
                                    {turn.kind === "judge_question" ? "问题已提交。" : "正在组织观点..."}
                                  </span>
                                )}
                              </div>

                              {turn.reasoning ? (
                                <details className="mt-3 border-t border-app-border pt-3">
                                  <summary className="cursor-pointer text-[13px] font-medium text-app-muted">
                                    查看思考摘要
                                  </summary>
                                  <div className="mt-2 whitespace-pre-wrap text-[13px] leading-6 text-app-muted">
                                    {turn.reasoning}
                                  </div>
                                </details>
                              ) : null}
                            </div>
                          </article>
                        );
                      })
                    )}
                  </div>
                </main>

                <aside className="min-h-0 overflow-y-auto bg-app-panel-soft/20">
                  <div className="border-b border-app-border px-6 py-5">
                    <div className="text-[12px] font-semibold tracking-[0.16em] text-app-muted uppercase">
                      控场
                    </div>
                    <div className="mt-2 text-[14px] leading-7 text-app-muted">
                      推进发言、插入问题、最后裁决，全部收在这一侧。
                    </div>
                    <button
                      className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-app-accent-soft px-4 py-3 text-[15px] font-semibold text-app-accent-strong transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={!canAdvance}
                      onClick={() => void handleNextTurn()}
                      type="button"
                    >
                      <Play className="size-4" />
                      {roomSession.stage === "judge_decision" ? "等待裁决" : "下一回合"}
                    </button>
                  </div>

                  <div className="border-b border-app-border px-6 py-5">
                    <div className="flex items-center gap-2 text-[16px] font-semibold text-app-text">
                      <MessageSquareQuote className="size-4" />
                      裁判追问
                    </div>
                    <select
                      className="mt-4 w-full rounded-xl border border-app-border bg-app-panel px-3 py-2 text-[14px] text-app-text outline-none transition focus:border-app-border-strong"
                      disabled={!canAsk}
                      onChange={(event) => setAskTarget(event.target.value as DebateAskTarget)}
                      value={askTarget}
                    >
                      <option value="all">双方都回答</option>
                      <option value="pro">只问正方</option>
                      <option value="con">只问反方</option>
                    </select>
                    <textarea
                      className="mt-3 min-h-[140px] w-full resize-none rounded-2xl border border-app-border bg-app-panel px-3 py-3 text-[14px] leading-7 text-app-text outline-none transition focus:border-app-border-strong"
                      disabled={!canAsk}
                      onChange={(event) => setAskQuestion(event.target.value)}
                      placeholder="例如：请双方重点讨论工作契约精神。"
                      value={askQuestion}
                    />
                    <button
                      className="mt-3 inline-flex w-full items-center justify-center rounded-xl bg-app-panel px-4 py-2.5 text-[14px] font-semibold text-app-text transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={!canAsk || !askQuestion.trim()}
                      onClick={() => void handleAsk()}
                      type="button"
                    >
                      立即追问
                    </button>
                  </div>

                  <div className="px-6 py-5">
                    <div className="flex items-center gap-2 text-[16px] font-semibold text-app-text">
                      <Trophy className="size-4" />
                      最终裁决
                    </div>
                    <select
                      className="mt-4 w-full rounded-xl border border-app-border bg-app-panel px-3 py-2 text-[14px] text-app-text outline-none transition focus:border-app-border-strong"
                      onChange={(event) => setWinner(event.target.value as DebateWinner)}
                      value={winner}
                    >
                      <option value="pro">正方获胜</option>
                      <option value="con">反方获胜</option>
                      <option value="draw">平局</option>
                    </select>

                    <div className="mt-3 grid grid-cols-2 gap-3">
                      <input
                        className="w-full rounded-xl border border-app-border bg-app-panel px-3 py-2 text-[14px] text-app-text outline-none transition focus:border-app-border-strong"
                        inputMode="numeric"
                        max="10"
                        min="0"
                        onChange={(event) => setProScore(event.target.value)}
                        placeholder="正方分数"
                        value={proScore}
                      />
                      <input
                        className="w-full rounded-xl border border-app-border bg-app-panel px-3 py-2 text-[14px] text-app-text outline-none transition focus:border-app-border-strong"
                        inputMode="numeric"
                        max="10"
                        min="0"
                        onChange={(event) => setConScore(event.target.value)}
                        placeholder="反方分数"
                        value={conScore}
                      />
                    </div>

                    <textarea
                      className="mt-3 min-h-[140px] w-full resize-none rounded-2xl border border-app-border bg-app-panel px-3 py-3 text-[14px] leading-7 text-app-text outline-none transition focus:border-app-border-strong"
                      onChange={(event) => setJudgeComment(event.target.value)}
                      placeholder="写下你的裁决理由。"
                      value={judgeComment}
                    />

                    <button
                      className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-[#f7ebe8] px-4 py-3 text-[15px] font-semibold text-[#9d3d32] transition hover:bg-[#f1dfdb] disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={runningAction !== null}
                      onClick={() => void handleDecision()}
                      type="button"
                    >
                      <Sparkles className="size-4" />
                      {roomSession.status === "finished" ? "更新裁决" : "结束并裁决"}
                    </button>

                    {roomSession.judge_decision ? (
                      <div className="mt-4 text-[14px] leading-7 text-app-muted">
                        当前结果：
                        <span className="ml-1 font-semibold text-app-text">
                          {WINNER_LABEL[roomSession.judge_decision.winner_side]}
                        </span>
                      </div>
                    ) : null}

                    {actionError ? (
                      <div className="mt-4 text-[14px] leading-7 text-[#9d3d32]">{actionError}</div>
                    ) : null}
                  </div>
                </aside>
              </div>

              {roomSession.summary ? (
                <div className="border-t border-app-border px-6 py-5 md:px-7">
                  <div className="flex items-center gap-2 text-[16px] font-semibold text-app-text">
                    <Sparkles className="size-4" />
                    结果总结
                  </div>
                  <div className="mt-3 whitespace-pre-wrap text-[14px] leading-7 text-app-muted">
                    {roomSession.summary}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
