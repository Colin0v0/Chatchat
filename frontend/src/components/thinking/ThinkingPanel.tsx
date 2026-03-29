import { ChevronRight } from "lucide-react";
import { useEffect, useRef } from "react";

interface ThinkingPanelProps {
  expanded: boolean;
  trace: string;
  onToggle: () => void;
}

export function ThinkingPanel({ expanded, trace, onToggle }: ThinkingPanelProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!expanded || !scrollRef.current) {
      return;
    }

    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [expanded, trace]);

  return (
    <div className="mb-3">
      <button
        aria-expanded={expanded}
        className="inline-flex min-h-[34px] items-center gap-2.5 py-[2px] text-app-muted/80 transition hover:text-app-muted"
        onClick={onToggle}
        type="button"
      >
        <span className="app-streaming-label text-[15px] italic tracking-[0.01em]">Thinking</span>
        <span aria-hidden="true" className="inline-flex items-center gap-1.25 self-center">
          <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.15s_infinite]" />
          <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.3s_infinite]" />
          <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.45s_infinite]" />
        </span>
        <ChevronRight className={`size-4 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`} />
      </button>

      <div
        className={`grid transition-[grid-template-rows,opacity,margin] duration-200 ${
          expanded ? "mt-3 grid-rows-[1fr] opacity-100" : "mt-0 grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="overflow-hidden">
          <div
            className="app-scrollbar max-h-[180px] overflow-y-auto border-l border-app-border pl-4 text-[14px] leading-7 text-app-muted/78"
            ref={scrollRef}
          >
            <div className="whitespace-pre-wrap break-words">{trace || "..."}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
