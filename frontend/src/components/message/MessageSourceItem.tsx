import type { MessageSource } from "../../types";
import { formatScore, getSourceBadges, getSourceLabel, getSourceMeta, toSourceHref } from "./sourceUtils";

interface MessageSourceItemProps {
  source: MessageSource;
}

export function MessageSourceItem({ source }: MessageSourceItemProps) {
  const scoreLabel = formatScore(source.score);
  const meta = getSourceMeta(source);
  const badges = getSourceBadges(source);

  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
      <div className="min-w-0">
        <a
          className="break-all underline-offset-2 transition hover:text-app-text hover:underline"
          href={toSourceHref(source)}
          rel="noreferrer"
          target="_blank"
          title={source.excerpt || source.url || source.path}
        >
          {getSourceLabel(source)}
        </a>
        {meta ? <span className="ml-1 text-app-muted/70">- {meta}</span> : null}
        {badges.length > 0 ? (
          <div className="mt-1 flex flex-wrap gap-1.5">
            {badges.map((badge) => (
              <span
                key={badge}
                className="rounded-full bg-app-panel-soft px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-app-muted/80"
              >
                {badge}
              </span>
            ))}
          </div>
        ) : null}
        {source.match_reason ? <div className="mt-1 text-app-muted/70">{source.match_reason}</div> : null}
      </div>
      {scoreLabel ? (
        <div className="shrink-0 text-[11px] font-medium tracking-[0.04em] text-app-muted/75">
          score {scoreLabel}
        </div>
      ) : null}
    </div>
  );
}
