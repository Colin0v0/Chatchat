import type { MessageSource } from "../../types";

interface MessageSourcesProps {
  sources: MessageSource[];
}

function formatScore(score: number | null | undefined): string | null {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return null;
  }
  return score.toFixed(2);
}

function toSourceHref(path: string): string {
  const trimmed = path.trim();
  if (/^[a-zA-Z]:[\\/]/.test(trimmed)) {
    return `file:///${trimmed.replace(/\\/g, "/")}`;
  }
  if (trimmed.startsWith("/")) {
    return `file://${trimmed}`;
  }
  return `obsidian://open?file=${encodeURIComponent(trimmed)}`;
}

export function MessageSources({ sources }: MessageSourcesProps) {
  if (sources.length === 0) {
    return null;
  }

  return (
    <section className="mt-4 space-y-2 text-[12px] leading-5 text-app-muted/90">
      <div className="font-medium tracking-[0.03em] text-app-muted/80">Sources</div>
      <div className="space-y-1.5">
        {sources.map((source, index) => {
          const scoreLabel = formatScore(source.score);
          return (
            <div
              key={`${source.path}-${source.heading}-${index}`}
              className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-3"
            >
              <div className="min-w-0">
                <a
                  className="break-all underline-offset-2 transition hover:text-app-text hover:underline"
                  href={toSourceHref(source.path)}
                  rel="noreferrer"
                  target="_blank"
                  title={source.excerpt || source.path}
                >
                  {source.path}
                </a>
                {source.heading ? <span className="ml-1 text-app-muted/70">- {source.heading}</span> : null}
              </div>
              {scoreLabel ? (
                <div className="shrink-0 text-[11px] font-medium tracking-[0.04em] text-app-muted/75">
                  score {scoreLabel}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}
