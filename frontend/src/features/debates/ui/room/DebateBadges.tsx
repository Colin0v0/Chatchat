import type { DebateParticipant, DebateSessionDetail, DebateTurn, DebateWinner } from "../../../../types";
import { STAGE_LABEL } from "../../lib/debateRoomConstants";
import { formatClock } from "../../lib/debateRoomUtils";

export function SideBadge({
  side,
  tone = "side",
}: {
  side: DebateParticipant["side"];
  tone?: "neutral" | "side" | "winner";
}) {
  const label = side === "pro" ? "正方" : "反方";
  const className =
    tone === "winner"
      ? "bg-app-accent-soft text-app-accent-strong"
      : tone === "neutral"
        ? "bg-app-accent-soft text-app-accent-strong"
        : side === "pro"
          ? "bg-[#e8f6ee] text-[#2f8f57]"
          : "bg-[#f7ebe8] text-[#9d3d32]";

  return (
    <span className={`inline-flex rounded-full px-2.5 py-1 text-[12px] font-semibold ${className}`}>
      {label}
    </span>
  );
}

export function StageBadge({ stage }: { stage: DebateTurn["stage"] | DebateSessionDetail["stage"] }) {
  return (
    <span className="inline-flex rounded-full bg-app-panel-strong px-2.5 py-1 text-[12px] font-semibold text-app-muted">
      {STAGE_LABEL[stage]}
    </span>
  );
}

function SideModelMeta({
  side,
  model,
  highlighted = false,
}: {
  side: DebateParticipant["side"];
  model: string;
  highlighted?: boolean;
}) {
  const alignClass = side === "con" ? "justify-self-end" : "justify-self-start";
  const rowClass = side === "con" ? "justify-end" : "justify-start";
  const dotClass = highlighted
    ? side === "pro"
      ? "bg-[#2f8f57]"
      : "bg-[#9d3d32]"
    : "bg-app-muted/45";
  const textClass = highlighted ? "text-app-text" : "text-app-text/88";

  return (
    <div className={`max-w-full ${alignClass}`}>
      <div className={`flex max-w-full items-center gap-2 ${rowClass}`}>
        {side === "pro" ? <span className={`size-2.5 shrink-0 rounded-full ${dotClass}`} /> : null}
        <span className={`truncate text-[16px] font-semibold tracking-[-0.02em] md:text-[17px] ${textClass}`}>
          {model}
        </span>
        {side === "con" ? <span className={`size-2.5 shrink-0 rounded-full ${dotClass}`} /> : null}
      </div>
    </div>
  );
}

function FreeDebateClockCard({
  active,
  label,
  remainingMs,
  side,
}: {
  active: boolean;
  label: string;
  remainingMs: number;
  side: DebateParticipant["side"];
}) {
  const isImminent = active && remainingMs <= 1_500;
  const isWarning = active && !isImminent && remainingMs <= 3_000;
  const accentClass = isImminent
    ? "border-[#c95b4b] bg-[#fff0ec]"
    : isWarning
      ? "border-[#b89b78] bg-[#f8f0de]"
      : side === "pro"
        ? active
          ? "border-app-accent-strong bg-app-accent-soft/70"
          : "border-app-border bg-app-panel-strong"
        : active
          ? "border-[#c77467] bg-[#f7ebe8]"
          : "border-app-border bg-app-panel-strong";
  const timerClass = isImminent
    ? "text-[#b44131] animate-pulse"
    : isWarning
      ? "text-[#8b673d]"
      : "text-app-text";
  const statusLabel = isImminent
    ? "即将截断"
    : isWarning
      ? "即将到时"
      : active
        ? "当前正在消耗时间"
        : "等待发言";
  const statusClass = isImminent
    ? "text-[#b44131]"
    : isWarning
      ? "text-[#8b673d]"
      : "text-app-muted";

  return (
    <div className={`rounded-[10px] border px-4 py-4 ${accentClass}`}>
      <div className={side === "con" ? "text-right" : ""}>
        <div className="text-[12px] font-semibold uppercase tracking-[0.08em] text-app-muted">{label}</div>
        <div className={`mt-2 text-[28px] font-semibold tracking-[-0.06em] ${timerClass}`}>
          {formatClock(remainingMs)}
        </div>
        <div className={`mt-1 text-[12px] font-semibold ${statusClass}`}>{statusLabel}</div>
      </div>
    </div>
  );
}

export function DebateStageHeader({
  showStageHeader,
  showStageTimer,
  stageTimerTitle,
  participantWinner,
  proModelLabel,
  conModelLabel,
  proRemainingMs,
  conRemainingMs,
  proActive,
  conActive,
}: {
  showStageHeader: boolean;
  showStageTimer: boolean;
  stageTimerTitle: string;
  participantWinner: DebateWinner | null;
  proModelLabel: string;
  conModelLabel: string;
  proRemainingMs: number;
  conRemainingMs: number;
  proActive: boolean;
  conActive: boolean;
}) {
  if (!showStageHeader) {
    return null;
  }

  return (
    <div className="border-b border-app-border px-6 py-4 md:px-7">
      <div className="grid gap-4">
        <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-6 px-1 py-1">
          <SideModelMeta
            highlighted={participantWinner === "pro"}
            model={proModelLabel}
            side="pro"
          />
          <div className="text-center text-[28px] font-semibold tracking-[-0.05em] text-app-text md:text-[32px]">
            {stageTimerTitle}
          </div>
          <SideModelMeta
            highlighted={participantWinner === "con"}
            model={conModelLabel}
            side="con"
          />
        </div>

        {showStageTimer ? (
          <div className="grid gap-3 md:grid-cols-2">
            <FreeDebateClockCard
              active={proActive}
              label="正方计时"
              remainingMs={proRemainingMs}
              side="pro"
            />
            <FreeDebateClockCard
              active={conActive}
              label="反方计时"
              remainingMs={conRemainingMs}
              side="con"
            />
          </div>
        ) : null}
      </div>
    </div>
  );
}
