import { ChevronDown, ChevronUp, LoaderCircle, MessageSquareQuote, Play, Scale, Sparkles, Trophy } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { streamDebateAsk, streamDebateNext, submitDebateDecision } from "../lib/api";
import { MarkdownMessage } from "./markdown/MarkdownMessage";
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

const DEBATER_LABELS = ["一辩", "二辩", "三辩", "四辩"];

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

function debaterLabel(index: number) {
  return DEBATER_LABELS[index] ?? `${index + 1}辩`;
}

function TurnCard({
  turn,
  participant,
}: {
  turn: DebateTurn;
  participant: DebateParticipant | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasContent = Boolean(turn.content);

  return (
    <article className="border-b border-app-border">
      {/* 头部行：点击折叠/展开 */}
      <button
        className="grid w-full grid-cols-1 gap-x-4 px-6 py-4 text-left transition hover:bg-app-panel-soft md:grid-cols-[136px_minmax(0,1fr)_auto]"
        onClick={() => setExpanded((v) => !v)}
        type="button"
      >
        {/* 左：说话人信息 */}
        <div className="mb-1 min-w-0 md:mb-0">
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
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                {participant ? <SideBadge side={participant.side} /> : null}
                <StageBadge stage={turn.stage} />
              </div>
            </>
          )}
        </div>

        {/* 中：内容预览（一行截断） */}
        <div className="min-w-0">
          {hasContent ? (
            <div className={`text-[14px] leading-6 text-app-text ${expanded ? "" : "truncate opacity-60"}`}>
              {expanded ? "" : turn.content}
            </div>
          ) : (
            <span className="text-[14px] text-app-muted">
              {turn.kind === "judge_question" ? "问题已提交。" : "正在组织观点..."}
            </span>
          )}
        </div>

        {/* 右：展开图标 */}
        <div className="hidden items-center md:flex">
          <ChevronDown
            className={`size-4 shrink-0 text-app-muted transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
          />
        </div>
      </button>

      {/* 展开内容 */}
      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out ${expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
      >
        <div className="overflow-hidden">
          <div className="px-6 pb-5 md:pl-[calc(136px+1rem)]">
            <div className="text-[15px] leading-8 text-app-text">
              {hasContent ? (
                <MarkdownMessage content={turn.content} />
              ) : null}
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
        </div>
      </div>
    </article>
  );
}

function ParticipantSlot({
  participant,
  label,
  side,
  emphasized = false,
}: {
  participant: DebateParticipant;
  label: string;
  side: DebateParticipant["side"];
  emphasized?: boolean;
}) {
  return (
    <div
      className={`w-full max-w-[220px] rounded-[8px] border px-3 py-3 transition sm:w-[220px] ${
        emphasized
          ? side === "pro"
            ? "border-app-accent-strong bg-app-accent-soft/60"
            : "border-[#c77467] bg-[#f7ebe8]"
          : "border-app-border bg-app-panel-strong"
      }`}
    >
      <div className={`text-[12px] font-semibold tracking-[0.08em] text-app-muted uppercase ${side === "con" ? "text-right" : ""}`}>
        {label}
      </div>
      <div className={`mt-2 truncate text-[14px] font-semibold text-app-text ${side === "con" ? "text-right" : ""}`}>
        {participant.model_id}
      </div>
    </div>
  );
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
  const [winner, setWinner] = useState<DebateWinner>(session.judge_decision?.winner_side ?? "pro");
  const [judgeComment, setJudgeComment] = useState(session.judge_decision?.judge_comment ?? "");
  const [proScore, setProScore] = useState(scoreValue(session.judge_decision?.scoring_json?.pro_score));
  const [conScore, setConScore] = useState(scoreValue(session.judge_decision?.scoring_json?.con_score));
  const [runningAction, setRunningAction] = useState<"next" | "ask" | "decision" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [controlsCollapsed, setControlsCollapsed] = useState(
    () => !(Array.isArray(session.turns) && session.turns.length > 0),
  );

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

  const canAdvance =
    runningAction === null && roomSession.stage !== "judge_decision" && roomSession.status !== "finished";
  const canAsk = runningAction === null && roomSession.status !== "finished";
  const currentStepIndex = FLOW_STEPS.findIndex((step) => step.stage === roomSession.stage);
  const latestSpeakerTurn = useMemo(
    () =>
      [...sortedTurns]
        .reverse()
        .find((turn) => turn.kind === "speaker_turn" && turn.speaker_participant_id != null) ?? null,
    [sortedTurns],
  );
  const activeSpeakerId = latestSpeakerTurn?.speaker_participant_id ?? null;
  const hasTurns = sortedTurns.length > 0;

  useEffect(() => {
    if (!hasTurns) {
      setControlsCollapsed(true);
    }
  }, [hasTurns]);

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
    <section className="flex min-h-0 flex-1 flex-col">
      <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto">
        <div className="flex min-h-full w-full flex-col">
          <div className="flex min-h-full flex-1 overflow-hidden border-t border-app-border bg-app-panel">
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="border-b border-app-border px-6 py-5 md:px-7">
                <div className="flex flex-wrap items-start justify-between gap-5">
                  <div className="min-w-0">
                    <div className="text-[28px] font-semibold tracking-[-0.05em] text-app-text">
                      {roomSession.topic}
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

              <div className="border-bottom border-app-border">
                <div className="grid items-start gap-5 border-b border-app-border px-6 py-5 xl:grid-cols-[minmax(0,1fr)_88px_minmax(0,1fr)] md:px-7">
                  <div className="min-w-0">
                    <div className="flex items-center">
                      <SideBadge side="pro" />
                    </div>
                    <div className="mt-3 grid justify-items-start">
                      {proParticipants.map((participant, index) => (
                        <ParticipantSlot
                          emphasized={participant.id === activeSpeakerId}
                          key={participant.id}
                          label={debaterLabel(index)}
                          participant={participant}
                          side="pro"
                        />
                      ))}
                    </div>
                  </div>

                  <div className="flex h-full min-h-[84px] flex-col items-center justify-center gap-3">
                    <div className="text-[50px] font-semibold tracking-[-0.08em] text-app-text/85">VS</div>
                    <StageBadge stage={roomSession.stage} />
                  </div>

                  <div className="min-w-[300px]">
                    <div className="flex items-center justify-start gap-2 xl:justify-end">
                      <SideBadge side="con" />
                    </div>
                    <div className="mt-3 grid justify-items-end gap-3">
                      {conParticipants.map((participant, index) => (
                        <ParticipantSlot
                          emphasized={participant.id === activeSpeakerId}
                          key={participant.id}
                          label={debaterLabel(index)}
                          participant={participant}
                          side="con"
                        />
                      ))}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-4 border-b border-app-border px-6 py-4 md:px-7">
                  {FLOW_STEPS.map((step, index) => {
                    const isActive = step.stage === roomSession.stage;
                    const isDone = currentStepIndex > index;
                    return (
                      <div className="flex items-center justify-center gap-2.5" key={step.stage}>
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
                          className={`text-[14px] ${
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

              <div className="relative flex min-h-0 flex-1 flex-col">
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
                  {!hasTurns ? (
                    <div className="flex min-h-full flex-col items-center justify-center px-8 pb-20 text-center">
                      <div className="text-[24px] font-semibold tracking-[-0.03em] text-app-text">
                        还没有发言记录
                      </div>
                      <div className="mt-2 text-[14px] text-app-muted">点击下方按钮开始第一回合辩论</div>
                      <button
                        className="mt-8 inline-flex items-center gap-2 rounded-[8px] bg-app-accent-soft px-6 py-3.5 text-[15px] font-semibold text-app-accent-strong transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-60"
                        disabled={!canAdvance}
                        onClick={() => void handleNextTurn()}
                        type="button"
                      >
                        <Play className="size-4" />
                        开始第一回合
                      </button>
                    </div>
                  ) : (
                    <>
                      {sortedTurns.map((turn) => {
                        const participant =
                          turn.speaker_participant_id != null
                            ? participantMap.get(turn.speaker_participant_id) ?? null
                            : null;

                        return (
                          <TurnCard
                            key={`${turn.id}`}
                            participant={participant}
                            turn={turn}
                          />
                        );
                      })}
                      {/* 结果总结放在滚动区末尾，裁判席上方 */}
                      {roomSession.summary ? (
                        <div className="border-b border-app-border px-6 py-6 md:px-7">
                          <div className="flex items-center gap-2 text-[15px] font-semibold text-app-text">
                            <Sparkles className="size-4 text-app-muted" />
                            结果总结
                          </div>
                          <div className="prose-debate mt-4 text-[14px] leading-7 text-app-text">
                            <MarkdownMessage content={roomSession.summary} />
                          </div>
                        </div>
                      ) : null}
                      {/* 底部留白，防止最后一条记录被悬浮裁判席遮挡 */}
                      <div className={`transition-[height] duration-300 ease-out ${controlsCollapsed ? "h-14" : "h-[310px]"}`} />
                    </>
                  )}
                </div>

                {/* 悬浮裁判席 */}
                <aside className="pointer-events-none absolute right-0 bottom-0 left-0 z-10">
                  <div className="pointer-events-auto mx-auto w-full max-w-[1080px]">
                    <div className="overflow-hidden rounded-t-[12px] border border-b-0 border-app-border bg-app-panel/96 shadow-[0_-4px_6px_-1px_rgba(34,24,16,0.05),0_-12px_36px_rgba(34,24,16,0.10)] backdrop-blur-md">

                      {/* 展开内容：grid-rows 丝滑动画 */}
                      <div
                        aria-hidden={controlsCollapsed}
                        className={`grid transition-[grid-template-rows] duration-300 ease-out ${
                          controlsCollapsed ? "grid-rows-[0fr]" : "grid-rows-[1fr]"
                        }`}
                      >
                        <div className="overflow-hidden">
                          {/* 三栏：裁决 左 | 下一回合 中 | 追问 右 */}
                          <div className="grid grid-cols-1 divide-y divide-app-border xl:grid-cols-[1fr_220px_1fr] xl:divide-x xl:divide-y-0">

                            {/* 左栏：最终裁决 */}
                            <div className="flex flex-col gap-3 px-6 py-5">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.06em] text-app-muted">
                                  <Trophy className="size-3.5" />
                                  最终裁决
                                </div>
                                {roomSession.judge_decision ? (
                                  <span className="rounded-full bg-app-accent-soft px-2.5 py-0.5 text-[12px] font-semibold text-app-accent-strong">
                                    {WINNER_LABEL[roomSession.judge_decision.winner_side]}获胜
                                  </span>
                                ) : null}
                              </div>

                              <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                                <input
                                  className="w-full rounded-[8px] border border-app-border bg-app-panel-strong px-3 py-2 text-[13px] text-app-text outline-none transition placeholder:text-app-muted focus:border-app-border-strong"
                                  inputMode="numeric"
                                  max="10"
                                  min="0"
                                  onChange={(event) => setProScore(event.target.value)}
                                  placeholder="正方分"
                                  value={proScore}
                                />
                                <select
                                  className="rounded-[8px] border border-app-border bg-app-panel-strong px-2 py-2 text-[13px] text-app-text outline-none transition focus:border-app-border-strong"
                                  onChange={(event) => setWinner(event.target.value as DebateWinner)}
                                  value={winner}
                                >
                                  <option value="pro">正方胜</option>
                                  <option value="con">反方胜</option>
                                  <option value="draw">平局</option>
                                </select>
                                <input
                                  className="w-full rounded-[8px] border border-app-border bg-app-panel-strong px-3 py-2 text-[13px] text-app-text outline-none transition placeholder:text-app-muted focus:border-app-border-strong"
                                  inputMode="numeric"
                                  max="10"
                                  min="0"
                                  onChange={(event) => setConScore(event.target.value)}
                                  placeholder="反方分"
                                  value={conScore}
                                />
                              </div>

                              <textarea
                                className="min-h-[80px] w-full resize-none rounded-[8px] border border-app-border bg-app-panel-strong px-3 py-2.5 text-[13px] leading-[1.6] text-app-text outline-none transition placeholder:text-app-muted focus:border-app-border-strong"
                                onChange={(event) => setJudgeComment(event.target.value)}
                                placeholder="写下你的裁决理由……"
                                value={judgeComment}
                              />

                              <button
                                className="inline-flex w-full items-center justify-center gap-2 rounded-[8px] bg-[#f7ebe8] px-4 py-2.5 text-[13px] font-semibold text-[#9d3d32] transition hover:bg-[#f1dfdb] disabled:cursor-not-allowed disabled:opacity-50"
                                disabled={runningAction !== null}
                                onClick={() => void handleDecision()}
                                type="button"
                              >
                                <Sparkles className="size-3.5" />
                                {roomSession.status === "finished" ? "更新裁决" : "结束并裁决"}
                              </button>

                              {actionError ? (
                                <div className="text-[12px] leading-5 text-[#9d3d32]">{actionError}</div>
                              ) : null}
                            </div>

                            {/* 中栏：下一回合 */}
                            <div className="flex flex-col items-center justify-center gap-4 px-6 py-5 xl:px-5">
                              <div className="flex flex-col items-center gap-1 text-center">
                                <div className="text-[12px] font-semibold uppercase tracking-[0.06em] text-app-muted">进程控制</div>
                                <StageBadge stage={roomSession.stage} />
                              </div>
                              <button
                                className="inline-flex w-full items-center justify-center gap-2 rounded-[8px] bg-app-accent-soft px-4 py-3 text-[14px] font-semibold text-app-accent-strong transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-50"
                                disabled={!canAdvance}
                                onClick={() => void handleNextTurn()}
                                type="button"
                              >
                                <Play className="size-4" />
                                {roomSession.stage === "judge_decision" ? "等待裁决" : "下一回合"}
                              </button>
                              {runningAction === "next" ? (
                                <div className="flex items-center gap-1.5 text-[12px] text-app-muted">
                                  <LoaderCircle className="size-3 animate-spin" />
                                  正在生成…
                                </div>
                              ) : null}
                            </div>

                            {/* 右栏：裁判追问 */}
                            <div className="flex flex-col gap-3 px-6 py-5">
                              <div className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.06em] text-app-muted">
                                <MessageSquareQuote className="size-3.5" />
                                裁判追问
                              </div>

                              <select
                                className="w-full rounded-[8px] border border-app-border bg-app-panel-strong px-3 py-2 text-[13px] text-app-text outline-none transition focus:border-app-border-strong disabled:opacity-50"
                                disabled={!canAsk}
                                onChange={(event) => setAskTarget(event.target.value as DebateAskTarget)}
                                value={askTarget}
                              >
                                <option value="all">双方都回答</option>
                                <option value="pro">只问正方</option>
                                <option value="con">只问反方</option>
                              </select>

                              <textarea
                                className="min-h-[80px] w-full resize-none rounded-[8px] border border-app-border bg-app-panel-strong px-3 py-2.5 text-[13px] leading-[1.6] text-app-text outline-none transition placeholder:text-app-muted focus:border-app-border-strong disabled:opacity-50"
                                disabled={!canAsk}
                                onChange={(event) => setAskQuestion(event.target.value)}
                                placeholder="例如：请双方重点讨论工作契约精神。"
                                value={askQuestion}
                              />

                              <button
                                className="inline-flex w-full items-center justify-center gap-2 rounded-[8px] border border-app-border bg-app-panel-strong px-4 py-2.5 text-[13px] font-semibold text-app-text transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-50"
                                disabled={!canAsk || !askQuestion.trim()}
                                onClick={() => void handleAsk()}
                                type="button"
                              >
                                {runningAction === "ask" ? (
                                  <LoaderCircle className="size-3.5 animate-spin" />
                                ) : (
                                  <MessageSquareQuote className="size-3.5" />
                                )}
                                立即追问
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* 收起 / 展开 toggle 条 */}
                      <button
                        aria-expanded={!controlsCollapsed}
                        className={`flex w-full items-center justify-between px-5 py-3 text-left transition hover:bg-app-panel-soft ${
                          controlsCollapsed ? "" : "border-t border-app-border"
                        }`}
                        onClick={() => setControlsCollapsed((current) => !current)}
                        type="button"
                      >
                        <span className="flex items-center gap-2 text-[13px] font-semibold text-app-text">
                          <Scale className="size-3.5 text-app-muted" />
                          裁判席
                        </span>
                        <span className="flex items-center gap-2 text-[12px] text-app-muted">
                          <span>{controlsCollapsed ? "展开" : "收起"}</span>
                          <ChevronUp
                            className={`size-4 transition-transform duration-300 ${controlsCollapsed ? "rotate-180" : ""}`}
                          />
                        </span>
                      </button>
                    </div>
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


