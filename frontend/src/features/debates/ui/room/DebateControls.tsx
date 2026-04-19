import { LoaderCircle, MessageSquareQuote, Play, Sparkles, Trophy } from "lucide-react";

import type { DebateAskTarget, DebateStage, DebateStatus } from "../../../../types";
import { ASK_TARGET_OPTIONS, STAGE_LABEL } from "../../lib/debateRoomConstants";

function getWinnerToggleClass(winner: "pro" | "con") {
  return winner === "pro"
    ? "border-[#8db89d] bg-[#e8f6ee] text-[#2f8f57]"
    : "border-[#d79a90] bg-[#f7ebe8] text-[#9d3d32]";
}

function getWinnerToggleLabel(winner: "pro" | "con") {
  return winner === "pro" ? "正方胜" : "反方胜";
}

function getAskTargetButtonLabel(option: DebateAskTarget, compact: boolean) {
  if (compact) {
    return ASK_TARGET_OPTIONS.find((item) => item.value === option)?.label ?? "";
  }

  if (option === "all") {
    return "都回答";
  }
  return option === "pro" ? "只问正方" : "只问反方";
}

function AdvancePanel({
  stage,
  canAdvance,
  runningAction,
  nextTurnLabel,
  nextTurnRunningLabel,
  onNextTurn,
  mobile,
}: {
  stage: DebateStage;
  canAdvance: boolean;
  runningAction: "next" | "ask" | "decision" | null;
  nextTurnLabel: string;
  nextTurnRunningLabel: string;
  onNextTurn: () => void;
  mobile: boolean;
}) {
  return (
    <div className={mobile ? "rounded-[14px] border border-app-border bg-[#fffdfa] px-4 py-4" : "flex h-full flex-col px-5 py-5"}>
      <div className="flex h-full flex-col justify-center gap-4 text-center">
        <div className="flex flex-col gap-1.5">
          <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-app-muted">当前阶段</div>
          <div className="text-[30px] font-semibold tracking-[-0.05em] text-app-text">{STAGE_LABEL[stage]}</div>
        </div>
        <button
          className={`inline-flex w-full items-center justify-center gap-2 ${mobile ? "rounded-[10px]" : "rounded-[8px]"} bg-app-accent-soft px-4 py-3 text-[14px] font-semibold text-app-accent-strong transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-50`}
          disabled={!canAdvance}
          onClick={onNextTurn}
          type="button"
        >
          {runningAction === "next" ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : stage === "judge_decision" ? (
            <Sparkles className="size-4" />
          ) : (
            <Play className="size-4" />
          )}
          {runningAction === "next" ? nextTurnRunningLabel : nextTurnLabel}
        </button>
      </div>
    </div>
  );
}

function DecisionPanel({
  winner,
  proScore,
  conScore,
  judgeComment,
  actionError,
  runningAction,
  status,
  onToggleWinner,
  onProScoreChange,
  onConScoreChange,
  onJudgeCommentChange,
  onDecision,
  mobile,
}: {
  winner: "pro" | "con";
  proScore: string;
  conScore: string;
  judgeComment: string;
  actionError: string | null;
  runningAction: "next" | "ask" | "decision" | null;
  status: DebateStatus;
  onToggleWinner: () => void;
  onProScoreChange: (value: string) => void;
  onConScoreChange: (value: string) => void;
  onJudgeCommentChange: (value: string) => void;
  onDecision: () => void;
  mobile: boolean;
}) {
  const winnerToggleClass = getWinnerToggleClass(winner);
  const winnerToggleLabel = getWinnerToggleLabel(winner);

  return (
    <div className={`flex h-full flex-col gap-3 ${mobile ? "rounded-[14px] border border-app-border bg-[#fffdfa] px-4 py-4" : "rounded-[8px] bg-[#fffdfa] px-5 py-4"}`}>
      <div className="flex h-full flex-col gap-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.06em] text-app-muted">
          <Trophy className="size-3.5" />
          最终裁决
        </div>

        <div className="grid grid-cols-3 items-center gap-2">
          <input
            className={`w-full ${mobile ? "rounded-[10px]" : "rounded-[8px]"} border border-app-border bg-app-panel px-3 py-2.5 text-[13px] text-app-text outline-none transition placeholder:text-app-muted focus:border-app-border-strong`}
            inputMode="numeric"
            max="100"
            min="0"
            onChange={(event) => onProScoreChange(event.target.value)}
            placeholder="正方分"
            value={proScore}
          />
          <button
            className={`w-full ${mobile ? "rounded-[10px]" : "rounded-[8px]"} border px-4 py-2.5 text-[12px] font-semibold transition ${winnerToggleClass}`}
            onClick={onToggleWinner}
            type="button"
          >
            {winnerToggleLabel}
          </button>
          <input
            className={`w-full ${mobile ? "rounded-[10px]" : "rounded-[8px]"} border border-app-border bg-app-panel px-3 py-2.5 text-right text-[13px] text-app-text outline-none transition placeholder:text-app-muted focus:border-app-border-strong`}
            inputMode="numeric"
            max="100"
            min="0"
            onChange={(event) => onConScoreChange(event.target.value)}
            placeholder="反方分"
            value={conScore}
          />
        </div>
        <textarea
          className={`${mobile ? "mt-2 min-h-[88px] rounded-[10px]" : "min-h-[116px] flex-1 rounded-[8px]"} w-full resize-none border border-app-border bg-app-panel px-3 py-3 text-[13px] leading-[1.6] text-app-text outline-none transition placeholder:text-app-muted focus:border-app-border-strong`}
          onChange={(event) => onJudgeCommentChange(event.target.value)}
          placeholder="写下你的裁决理由…"
          value={judgeComment}
        />

        <button
          className={`inline-flex w-full items-center justify-center gap-2 ${mobile ? "rounded-[10px] text-[14px]" : "rounded-[8px] text-[13px]"} bg-[#f7ebe8] px-4 py-3 font-semibold text-[#9d3d32] transition hover:bg-[#f1dfdb] disabled:cursor-not-allowed disabled:opacity-50`}
          disabled={runningAction !== null}
          onClick={onDecision}
          type="button"
        >
          <Sparkles className="size-3.5" />
          {status === "finished" ? "更新裁决" : "结束并裁决"}
        </button>

        {actionError ? <div className="text-[12px] leading-5 text-[#9d3d32]">{actionError}</div> : null}
      </div>
    </div>
  );
}

function AskPanel({
  askTarget,
  askQuestion,
  canAsk,
  runningAction,
  onAskTargetChange,
  onAskQuestionChange,
  onAsk,
  mobile,
}: {
  askTarget: DebateAskTarget;
  askQuestion: string;
  canAsk: boolean;
  runningAction: "next" | "ask" | "decision" | null;
  onAskTargetChange: (value: DebateAskTarget) => void;
  onAskQuestionChange: (value: string) => void;
  onAsk: () => void;
  mobile: boolean;
}) {
  return (
    <div className={`flex h-full flex-col gap-3 ${mobile ? "rounded-[14px] border border-app-border bg-[#fffdfa] px-4 py-4" : "rounded-[8px] bg-[#fffdfa] px-5 py-4"}`}>
      <div className="flex h-full flex-col gap-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold uppercase tracking-[0.06em] text-app-muted">
          <MessageSquareQuote className="size-3.5" />
          裁判追问
        </div>

        <div className="grid grid-cols-3 gap-2">
          {ASK_TARGET_OPTIONS.map((option) => {
            const active = askTarget === option.value;
            return (
              <button
                className={`${mobile ? "rounded-[10px] px-2" : "rounded-[8px] px-3"} border py-2 text-[12px] font-semibold transition ${
                  active
                    ? "border-[#b89b78] bg-[#efe4d2] text-[#7c5f3b]"
                    : "border-app-border bg-app-panel text-app-muted hover:bg-app-panel-soft"
                }`}
                disabled={!canAsk}
                key={option.value}
                onClick={() => onAskTargetChange(option.value)}
                type="button"
              >
                {getAskTargetButtonLabel(option.value, mobile)}
              </button>
            );
          })}
        </div>

        <textarea
          className={`${mobile ? "mt-3 min-h-[88px] rounded-[10px]" : "min-h-[116px] flex-1 rounded-[8px]"} w-full resize-none border border-app-border bg-app-panel px-3 py-3 text-[13px] leading-[1.6] text-app-text outline-none transition placeholder:text-app-muted focus:border-app-border-strong disabled:opacity-50`}
          disabled={!canAsk}
          onChange={(event) => onAskQuestionChange(event.target.value)}
          placeholder="写下你想问的问题..."
          value={askQuestion}
        />

        <button
          className={`inline-flex w-full items-center justify-center gap-2 ${mobile ? "rounded-[10px] text-[14px]" : "rounded-[8px] text-[13px]"} border border-app-border bg-app-panel px-4 py-3 font-semibold text-app-text transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-50`}
          disabled={!canAsk || !askQuestion.trim()}
          onClick={onAsk}
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
  );
}

export function DebateControls({
  stage,
  status,
  canAdvance,
  canAsk,
  runningAction,
  nextTurnLabel,
  nextTurnRunningLabel,
  winner,
  proScore,
  conScore,
  judgeComment,
  actionError,
  askTarget,
  askQuestion,
  onToggleWinner,
  onProScoreChange,
  onConScoreChange,
  onJudgeCommentChange,
  onAskTargetChange,
  onAskQuestionChange,
  onNextTurn,
  onDecision,
  onAsk,
}: {
  stage: DebateStage;
  status: DebateStatus;
  canAdvance: boolean;
  canAsk: boolean;
  runningAction: "next" | "ask" | "decision" | null;
  nextTurnLabel: string;
  nextTurnRunningLabel: string;
  winner: "pro" | "con";
  proScore: string;
  conScore: string;
  judgeComment: string;
  actionError: string | null;
  askTarget: DebateAskTarget;
  askQuestion: string;
  onToggleWinner: () => void;
  onProScoreChange: (value: string) => void;
  onConScoreChange: (value: string) => void;
  onJudgeCommentChange: (value: string) => void;
  onAskTargetChange: (value: DebateAskTarget) => void;
  onAskQuestionChange: (value: string) => void;
  onNextTurn: () => void;
  onDecision: () => void;
  onAsk: () => void;
}) {
  return (
    <aside className="shrink-0 border-t border-app-border bg-app-panel/96 backdrop-blur-md">
      <div className="w-full">
        <div className="overflow-visible opacity-100">
          <div className="translate-y-0">
            <div className="space-y-3 p-3 lg:hidden">
              <AdvancePanel
                canAdvance={canAdvance}
                mobile
                nextTurnLabel={nextTurnLabel}
                nextTurnRunningLabel={nextTurnRunningLabel}
                onNextTurn={onNextTurn}
                runningAction={runningAction}
                stage={stage}
              />
              <DecisionPanel
                actionError={actionError}
                conScore={conScore}
                judgeComment={judgeComment}
                mobile
                onConScoreChange={onConScoreChange}
                onDecision={onDecision}
                onJudgeCommentChange={onJudgeCommentChange}
                onProScoreChange={onProScoreChange}
                onToggleWinner={onToggleWinner}
                proScore={proScore}
                runningAction={runningAction}
                status={status}
                winner={winner}
              />
              <AskPanel
                askQuestion={askQuestion}
                askTarget={askTarget}
                canAsk={canAsk}
                mobile
                onAsk={onAsk}
                onAskQuestionChange={onAskQuestionChange}
                onAskTargetChange={onAskTargetChange}
                runningAction={runningAction}
              />
            </div>

            <div className="hidden gap-4 px-4 lg:grid lg:grid-cols-[minmax(0,1fr)_220px_minmax(0,1fr)] lg:items-stretch">
              <DecisionPanel
                actionError={actionError}
                conScore={conScore}
                judgeComment={judgeComment}
                mobile={false}
                onConScoreChange={onConScoreChange}
                onDecision={onDecision}
                onJudgeCommentChange={onJudgeCommentChange}
                onProScoreChange={onProScoreChange}
                onToggleWinner={onToggleWinner}
                proScore={proScore}
                runningAction={runningAction}
                status={status}
                winner={winner}
              />
              <AdvancePanel
                canAdvance={canAdvance}
                mobile={false}
                nextTurnLabel={nextTurnLabel}
                nextTurnRunningLabel={nextTurnRunningLabel}
                onNextTurn={onNextTurn}
                runningAction={runningAction}
                stage={stage}
              />
              <AskPanel
                askQuestion={askQuestion}
                askTarget={askTarget}
                canAsk={canAsk}
                mobile={false}
                onAsk={onAsk}
                onAskQuestionChange={onAskQuestionChange}
                onAskTargetChange={onAskTargetChange}
                runningAction={runningAction}
              />
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
