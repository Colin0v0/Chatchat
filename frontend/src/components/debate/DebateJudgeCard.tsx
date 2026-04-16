import { ChevronDown, Sparkles, Trophy } from "lucide-react";

import type { DebateJudgeAnalysis, DebateStageScoreKey, DebateWinner } from "../../types";
import { MarkdownMessage } from "../markdown/MarkdownMessage";

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

  return (
    <div className="rounded-[8px] border border-app-border bg-app-panel px-4 py-4">
      <div className="grid grid-cols-[minmax(0,1fr)_64px_64px] items-center gap-x-2 gap-y-2">
        <div className="text-[12px] font-semibold text-app-muted">阶段判分</div>
        <div className="text-center text-[11px] font-semibold text-app-muted">正</div>
        <div className="text-center text-[11px] font-semibold text-app-muted">反</div>
        {stageScores.map((item) => (
          <div className="contents" key={item.key}>
            <div className="text-[13px] text-app-text">{item.label}</div>
            <div className="text-center text-[13px] font-semibold text-app-text">{item.pro ?? "-"}</div>
            <div className="text-center text-[13px] font-semibold text-app-text">{item.con ?? "-"}</div>
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
  onToggle,
  stageScores,
  winner,
}: {
  analysis: DebateJudgeAnalysis;
  analysisMarkdown: string;
  expanded: boolean;
  judgeComment: string;
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
