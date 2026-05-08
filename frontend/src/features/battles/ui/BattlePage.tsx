import {
  ArrowLeft,
  ArrowRight,
  Ban,
  Check,
  Copy,
  Expand,
  LoaderCircle,
  Swords,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ComponentProps, type ReactNode } from "react";

import { ChatComposer } from "../../chats/ui/ChatComposer";
import { MarkdownMessage } from "../../chats/ui/markdown/MarkdownMessage";
import { MessageAttachmentStrip } from "../../chats/ui/message/MessageAttachmentStrip";
import { ModelProviderIcon } from "../../models/ui/model-icons/ModelProviderIcon";
import type { BattleRound, BattleSessionDetail, BattleSideId, BattleSideState, BattleVote } from "../model/types";

interface BattlePageProps {
  composerProps: ComponentProps<typeof ChatComposer>;
  isStreaming: boolean;
  session: BattleSessionDetail | null;
  onVote: (roundId: string, vote: BattleVote) => void;
}

function voteSelectsSide(vote: BattleVote | null, side: BattleSideId) {
  if (vote === side) {
    return true;
  }
  return vote === "both_good";
}

function sideIsSettled(side: BattleSideState) {
  return side.status === "done" || side.status === "error";
}

function BattleAnswerCard({
  revealed,
  selected,
  side,
}: {
  revealed: boolean;
  selected: boolean;
  side: BattleSideState;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const title = revealed ? side.model.label : `Assistant ${side.id.toUpperCase()}`;
  const elapsedMs = side.finishedAt && side.startedAt ? side.finishedAt - side.startedAt : null;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(side.content || side.error || "");
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      // ignore
    }
  }

  const card = (
    <article
      className={[
        "overflow-hidden rounded-[14px] border bg-white text-[#33302c] transition-colors",
        selected ? "border-[#2f9e44]" : "border-[#ece9e4]",
      ].join(" ")}
    >
      <div
        className={[
          "flex h-14 items-center justify-between gap-3 border-b px-5",
          selected ? "border-[#d8efd9]" : "border-[#ece9e4]",
        ].join(" ")}
      >
        <div className="flex min-w-0 items-center gap-3">
          {revealed ? (
            <span className="flex size-5 shrink-0 items-center justify-center">
              <ModelProviderIcon model={side.model} />
            </span>
          ) : (
            <span className="size-4 shrink-0 rounded-full bg-[#1f2027]" />
          )}
          <span
            className={[
              "min-w-0 truncate text-[15px] font-medium",
              revealed && selected ? "text-[#2f9e44]" : "text-[#2f2d29]",
            ].join(" ")}
          >
            {title}
          </span>
          {revealed && elapsedMs ? (
            <span className="shrink-0 text-[12px] text-[#8f8981]">{Math.max(0.1, elapsedMs / 1000).toFixed(1)}s</span>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-2 text-[#55514b]">
          {side.status === "streaming" ? <LoaderCircle className="size-4 animate-spin" /> : null}
          {side.status === "error" ? <Ban className="size-4 text-[#9d3d32]" /> : null}
          <button
            aria-label={copied ? "Copied" : "Copy answer"}
            className="flex size-8 items-center justify-center rounded-[8px] transition hover:bg-[#f4f2ef]"
            onClick={() => void handleCopy()}
            type="button"
          >
            {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
          </button>
          <button
            aria-label="Expand answer"
            className="flex size-8 items-center justify-center rounded-[8px] transition hover:bg-[#f4f2ef]"
            onClick={() => setExpanded(true)}
            type="button"
          >
            <Expand className="size-4" />
          </button>
        </div>
      </div>

      <div className="min-h-[100px] px-5 py-5 text-[15px] leading-7">
        {side.status === "error" ? (
          <div className="text-[#9d3d32]">{side.error}</div>
        ) : side.content ? (
          <MarkdownMessage content={side.content} />
        ) : (
          <div className="text-[#a6a19b]">Generating...</div>
        )}
      </div>
    </article>
  );

  return (
    <>
      {card}
      {expanded ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 px-4 py-6 backdrop-blur-[4px]"
          onClick={() => setExpanded(false)}
        >
          <div
            className="flex max-h-full w-full max-w-[980px] flex-col overflow-hidden rounded-[16px] border border-[#ece9e4] bg-white shadow-[0_24px_80px_rgba(25,22,18,0.20)]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex h-14 items-center justify-between border-b border-[#ece9e4] px-5">
              <div className="min-w-0 truncate text-[15px] font-medium">{title}</div>
              <button
                aria-label="Close expanded answer"
                className="flex size-9 items-center justify-center rounded-[8px] hover:bg-[#f4f2ef]"
                onClick={() => setExpanded(false)}
                type="button"
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="app-scrollbar overflow-y-auto px-6 py-6 text-[15px] leading-7">
              {side.content ? <MarkdownMessage content={side.content} /> : <div className="text-[#a6a19b]">Generating...</div>}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function VoteButton({
  active,
  children,
  disabled,
  onClick,
}: {
  active: boolean;
  children: ReactNode;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={[
        "flex h-11 min-w-0 flex-1 items-center justify-center gap-2 rounded-[8px] border px-3 text-[15px] font-medium transition",
        active
          ? "border-[#2f9e44] bg-[#eaf7ea] text-[#267a35]"
          : "border-[#dedbd6] bg-white text-[#3b3935] hover:border-[#cfcac2] hover:bg-[#fbfaf8]",
        disabled ? "cursor-not-allowed opacity-55" : "",
      ].join(" ")}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}

function BattleVoteBar({
  isStreaming,
  round,
  onVote,
}: {
  isStreaming: boolean;
  round: BattleRound | null;
  onVote: (roundId: string, vote: BattleVote) => void;
}) {
  const ready = Boolean(round && sideIsSettled(round.sides.a) && sideIsSettled(round.sides.b));
  const disabled = isStreaming || !round || !ready;
  if (!ready || round?.vote) return null;

  return (
    <div className="grid w-full grid-cols-2 gap-2 rounded-[12px] border border-[#e6e1da] bg-[#f6f3ee] p-3 md:grid-cols-4">
      <VoteButton active={round?.vote === "a"} disabled={disabled} onClick={() => round && onVote(round.id, "a")}>
        <ArrowLeft className="size-4 shrink-0" />
        <span>A 更好</span>
      </VoteButton>
      <VoteButton active={round?.vote === "both_good"} disabled={disabled} onClick={() => round && onVote(round.id, "both_good")}>
        <Check className="size-4 shrink-0" />
        <span>都不错</span>
      </VoteButton>
      <VoteButton active={round?.vote === "both_bad"} disabled={disabled} onClick={() => round && onVote(round.id, "both_bad")}>
        <Ban className="size-4 shrink-0" />
        <span>都不好</span>
      </VoteButton>
      <VoteButton active={round?.vote === "b"} disabled={disabled} onClick={() => round && onVote(round.id, "b")}>
        <span>B 更好</span>
        <ArrowRight className="size-4 shrink-0" />
      </VoteButton>
    </div>
  );
}

function BattleRoundView({ round }: { round: BattleRound }) {
  return (
    <div className="space-y-7">
      <div className="flex flex-col items-end gap-2">
        <MessageAttachmentStrip align="end" attachments={round.attachments ?? []} />
        <div className="w-fit max-w-[420px] min-w-0 self-end rounded-[18px] bg-app-panel-soft px-4 py-1.75 text-left text-[15px] leading-7 text-app-accent-strong">
          {round.prompt}
        </div>
      </div>

      <div className="grid gap-7 md:grid-cols-2">
        <BattleAnswerCard
          revealed={round.revealed}
          selected={voteSelectsSide(round.vote, "a")}
          side={round.sides.a}
        />
        <BattleAnswerCard
          revealed={round.revealed}
          selected={voteSelectsSide(round.vote, "b")}
          side={round.sides.b}
        />
      </div>
    </div>
  );
}

export function BattlePage({
  composerProps,
  isStreaming,
  session,
  onVote,
}: BattlePageProps) {
  const latestRound = session?.rounds.at(-1) ?? null;
  const hasRounds = Boolean(session?.rounds.length);
  const placeholder = hasRounds ? "Ask followup..." : "Ask anything...";
  const scrollRef = useRef<HTMLDivElement>(null);

  const rounds = useMemo(() => session?.rounds ?? [], [session]);
  const pendingScrollRef = useRef(false);

  useEffect(() => {
    pendingScrollRef.current = true;
  }, [session?.id]);

  useEffect(() => {
    if (!scrollRef.current || !pendingScrollRef.current) {
      return;
    }
    const frame = window.requestAnimationFrame(() => {
      scrollRef.current!.scrollTop = scrollRef.current!.scrollHeight;
      pendingScrollRef.current = false;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [rounds]);

  return (
    <section className="flex min-h-0 flex-1 flex-col pb-1 bg-[#fdfcfb] text-[#2f2d29]">
      <div ref={scrollRef} className="app-scrollbar min-h-0 flex-1 overflow-y-auto pt-4">
        <div className="mx-auto w-full max-w-[920px] px-4 md:px-6" data-pet-anchor="messageArea">
          {rounds.length > 0 ? (
            <div className="space-y-12">
              {rounds.map((round) => (
                <BattleRoundView key={round.id} round={round} />
              ))}
            </div>
          ) : (
            <div className="flex h-full min-h-[360px] items-center justify-center px-6 text-center">
              <div className="max-w-[520px]">
                <div className="mx-auto flex size-14 items-center justify-center rounded-full border border-[#ece9e4] bg-white text-[#2f2d29]">
                  <Swords className="size-6" />
                </div>
                <div className="mt-5 text-[30px] font-semibold tracking-[-0.03em]">Chatchat: Battle</div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mx-auto w-full max-w-[920px] px-4 pt-2 md:px-6">
        {latestRound?.vote === null ? (
          <div className="mb-2">
            <BattleVoteBar isStreaming={isStreaming} onVote={onVote} round={latestRound} />
          </div>
        ) : null}
        <ChatComposer
          {...composerProps}
          attachmentAcceptOverride="image/png,image/jpeg,image/webp,image/gif,.pdf,.txt,.md,.csv,.json,.doc,.docx,.ppt,.pptx,.xls,.xlsx"
          centered={false}
          placeholder={placeholder}
          showImageModeOption={false}
          showModelControls={false}
          showNewDebateOption={false}
          showVoiceInput={false}
        />
      </div>
    </section>
  );
}
