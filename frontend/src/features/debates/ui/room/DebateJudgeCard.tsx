import { ChevronDown, Sparkles, Trophy } from "lucide-react";

import type { DebateJudgeAnalysis, DebateStageScoreKey, DebateWinner } from "../../../../types";
import { MarkdownMessage } from "../../../chats/ui/markdown/MarkdownMessage";

function JudgeSection({
  title,
  content,
}: {
  title: string;
  content: string;
}) {
  if (!content.trim()) {
    return null;
  }

  return (
    <div className="space-y-1.5">
      <div className="text-[13px] font-semibold text-app-text">{title}</div>
      <div className="text-[14px] leading-7 text-app-text">{content}</div>
    </div>
  );
}

function ScoreTable({
  stageScores,
}: {
  stageScores: Array<{
    key: DebateStageScoreKey;
    label: string;
    pro: number | null;
    con: number | null;
  }>;
}) {
  if (!stageScores.length) {
    return null;
  }

  function toPercent(score: number | null) {
    if (score == null) {
      return 0;
    }
    return Math.max(0, Math.min(100, (score / 25) * 100));
  }

  return (
    <div className="rounded-[8px] border border-app-border bg-app-panel px-4 py-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-[12px] font-semibold text-app-muted">阶段判分</div>
        <div className="text-[11px] font-medium text-app-muted">单阶段满分 25</div>
      </div>
      <div className="space-y-3">
        {stageScores.map((item) => (
          <div
            className="rounded-[12px] border border-app-border/80 bg-[#f6f1e8] px-3 py-3"
            key={item.key}
          >
            <div className="text-[13px] font-semibold text-app-text">{item.label}</div>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              <div>
                <div className="mb-1.5 flex items-center justify-between text-[11px] font-medium text-[#2f8f57]">
                  <span>正方</span>
                  <span>{item.pro ?? "-"}</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-[#dcebdc]">
                  <div
                    className="h-full rounded-full bg-[#2f8f57] transition-[width] duration-300 ease-out"
                    style={{ width: `${toPercent(item.pro)}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="mb-1.5 flex items-center justify-between text-[11px] font-medium text-[#9d3d32]">
                  <span className="order-2 md:order-1">{item.con ?? "-"}</span>
                  <span className="order-1 md:order-2">反方</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-[#f1ddd9]">
                  <div
                    className="h-full rounded-full bg-[#c6654d] transition-[width] duration-300 ease-out md:ml-auto"
                    style={{ width: `${toPercent(item.con)}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DebateJudgeCard({
  analysis,
  analysisMarkdown,
  expanded,
  judgeComment,
  partial = false,
  pending = false,
  onToggle,
  stageScores,
  winner,
}: {
  analysis: DebateJudgeAnalysis;
  analysisMarkdown: string;
  expanded: boolean;
  judgeComment: string;
  partial?: boolean;
  pending?: boolean;
  onToggle: () => void;
  stageScores: Array<{
    key: DebateStageScoreKey;
    label: string;
    pro: number | null;
    con: number | null;
  }>;
  winner: DebateWinner | null;
}) {
  const hasAnalysis = Object.values(analysis).some((value) => value.trim());
  const hasMarkdown = analysisMarkdown.trim().length > 0;
  const hasContent = hasAnalysis || hasMarkdown || !!judgeComment.trim() || stageScores.length > 0 || winner != null;

  if (!hasContent) {
    return null;
  }

  return (
    <div className="border-b border-app-border">
      <button
        className="grid h-[75.5px] w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 px-6 py-0 text-left transition hover:bg-app-panel-soft"
        onClick={onToggle}
        type="button"
      >
        <span className="flex items-center gap-2 text-[15px] font-semibold text-app-text">
          <Sparkles className="size-4 text-app-muted" />
          AI评委
          {partial ? (
            <span className="inline-flex items-center rounded-full bg-[#f4e7db] px-2 py-0.5 text-[11px] font-medium text-[#8a5b33]">
              未完成
            </span>
          ) : null}
        </span>
        <div className="flex items-center">
          <ChevronDown
            className={`size-4 shrink-0 text-app-muted transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
          />
        </div>
      </button>
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
      >
        <div className="overflow-hidden">
          <div className="space-y-5 px-6 py-3">
            {partial ? (
              <div className="rounded-[8px] border border-[#ead8c8] bg-[#fdf5ef] px-4 py-3 text-[13px] leading-6 text-[#8a5b33]">
                这份讲评没有拿到最终评分结果，当前只保留已收到的部分内容；可继续评分补全。
              </div>
            ) : null}
            {hasMarkdown ? (
              <div className="prose-debate text-[14px] leading-7 text-app-text">
                <MarkdownMessage content={analysisMarkdown} />
              </div>
            ) : (
              <>
                <JudgeSection title="裁决摘要" content={judgeComment} />
                <JudgeSection title="正方评价" content={analysis.pro_review} />
                <JudgeSection title="反方评价" content={analysis.con_review} />
                <JudgeSection title="双方共同表现" content={analysis.shared_feedback} />
                <JudgeSection title="关键胜负手" content={analysis.key_decision} />

                {analysis.final_vote.trim() || winner ? (
                  <div className="rounded-[8px] bg-app-panel px-4 py-3">
                    <div className="flex items-center gap-2 text-[13px] font-semibold text-app-text">
                      <Trophy className="size-3.5 text-app-muted" />
                      最终投票
                    </div>
                    <div className="mt-1 text-[14px] leading-7 text-app-text">
                      {analysis.final_vote.trim() ||
                        (winner === "pro" ? "本场我投正方一票" : "本场我投反方一票")}
                    </div>
                  </div>
                ) : null}
              </>
            )}

            <ScoreTable stageScores={stageScores} />
          </div>
        </div>
      </div>
    </div>
  );
}
