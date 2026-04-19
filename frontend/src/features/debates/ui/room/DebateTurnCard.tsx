import { Check, ChevronDown, Copy, LoaderCircle } from "lucide-react";
import { useState } from "react";

import type { DebateParticipant, DebateTurn } from "../../../../types";
import { STAGE_LABEL } from "../../lib/debateRoomConstants";
import { SideBadge, StageBadge } from "./DebateBadges";
import { MarkdownMessage } from "../../../chats/ui/markdown/MarkdownMessage";

export function DebateTurnCard({
  turn,
  participant,
  isStreaming = false,
  isFinalizingTimeout = false,
  sequenceNumber = null,
}: {
  turn: DebateTurn;
  participant: DebateParticipant | null;
  isStreaming?: boolean;
  isFinalizingTimeout?: boolean;
  sequenceNumber?: number | null;
}) {
  const [expanded, setExpanded] = useState(true);
  const [copied, setCopied] = useState(false);
  const hasContent = Boolean(turn.content);
  const showStreamingState = isStreaming && turn.kind === "speaker_turn" && !isFinalizingTimeout;
  const showTimeoutFinalizingState = isFinalizingTimeout && turn.kind === "speaker_turn";
  const showSequenceBadge =
    turn.kind === "speaker_turn" && turn.stage === "free_debate" && sequenceNumber != null;

  async function handleCopy() {
    if (!turn.content.trim()) {
      return;
    }

    try {
      await navigator.clipboard.writeText(turn.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

  return (
    <article className="border-b border-app-border">
      <div className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 px-6 py-3 transition hover:bg-app-panel-soft">
        <button
          className="mb-1 min-w-0 text-left md:mb-0"
          onClick={() => setExpanded((value) => !value)}
          type="button"
        >
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
                {showSequenceBadge ? (
                  <span className="inline-flex rounded-full bg-[#efe6d8] px-2 py-1 text-[11px] font-semibold text-app-text">
                    第 {sequenceNumber} 轮
                  </span>
                ) : null}
                {showStreamingState ? <LoaderCircle className="size-3.5 animate-spin text-app-muted" /> : null}
                {showTimeoutFinalizingState ? (
                  <span className="inline-flex rounded-full bg-[#f7ebe8] px-2 py-1 text-[11px] font-semibold text-[#9d3d32]">
                    截断收尾中
                  </span>
                ) : null}
                {turn.elapsed_ms ? (
                  <span className="text-[12px] text-app-muted">{(turn.elapsed_ms / 1000).toFixed(1)}s</span>
                ) : null}
                {turn.truncated ? (
                  <span className="inline-flex rounded-full bg-[#f7ebe8] px-2 py-1 text-[11px] font-semibold text-[#9d3d32]">
                    超时截断
                  </span>
                ) : null}
              </div>
            </>
          )}
        </button>

        <div className="flex items-center self-center gap-1.5">
          {hasContent ? (
            <button
              aria-label="复制辩词"
              className="flex h-9 w-9 items-center justify-center rounded-xl text-app-muted transition hover:text-app-text"
              onClick={() => void handleCopy()}
              title={copied ? "已复制" : "复制辩词"}
              type="button"
            >
              {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
            </button>
          ) : null}
          <button
            aria-label={expanded ? "收起发言" : "展开发言"}
            className="flex h-9 w-9 items-center justify-center rounded-xl text-app-muted transition hover:text-app-text"
            onClick={() => setExpanded((value) => !value)}
            type="button"
          >
            <ChevronDown
              className={`size-4 shrink-0 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
            />
          </button>
        </div>
      </div>

      <div
        className={`grid transition-[grid-template-rows] duration-200 ease-out ${expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}
      >
        <div className="overflow-hidden">
          <div className="px-6 py-3">
            <div className="text-[15px] leading-8 text-app-text">
              {hasContent ? (
                <MarkdownMessage content={turn.content} />
              ) : showTimeoutFinalizingState ? (
                <span className="inline-flex shrink-0 whitespace-nowrap text-[15px] leading-[1.4] tracking-[0.01em] text-[#9d3d32]/80">
                  正在按时限截断...
                </span>
              ) : showStreamingState ? (
                <div className="inline-flex items-center gap-2.5 text-app-muted/80">
                  <span className="inline-flex shrink-0 whitespace-nowrap text-[15px] leading-[1.4] tracking-[0.01em]">
                    正在生成...
                  </span>
                  <div aria-hidden="true" className="inline-flex items-center gap-1.25 self-center">
                    <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.15s_infinite]" />
                    <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.3s_infinite]" />
                    <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.45s_infinite]" />
                  </div>
                </div>
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
