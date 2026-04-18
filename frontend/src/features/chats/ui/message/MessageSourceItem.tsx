import type { MessageSource } from "../../../../types";
import { formatScore, getSourceLabel, getSourceMeta, toSourceHref } from "./sourceUtils";

interface MessageSourceItemProps {
  source: MessageSource;
}

export function MessageSourceItem({ source }: MessageSourceItemProps) {
  const scoreLabel = formatScore(source.score);
  const meta = getSourceMeta(source);
  const isWebSource = source.type === "web";
  const label = getSourceLabel(source);

  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
      <div className="min-w-0">
        {!isWebSource ? <div className="text-[13px] font-medium tracking-[0.02em] text-app-text">{label}</div> : null}
        {meta ? (
          <a
            className={`${isWebSource ? "" : "mt-1 "}block break-all text-app-muted/75 underline-offset-2 transition hover:text-app-text hover:underline`}
            href={toSourceHref(source)}
            rel="noreferrer"
            target="_blank"
            title={source.excerpt || source.url || source.path}
          >
            {meta}
          </a>
        ) : null}
        {!isWebSource && source.match_reason ? <div className="mt-1 text-app-muted/70">{source.match_reason}</div> : null}
      </div>
      {scoreLabel ? (
        <div className="shrink-0 text-[11px] font-medium tracking-[0.04em] text-app-muted/75">
          置信度 {scoreLabel}
        </div>
      ) : null}
    </div>
  );
}
