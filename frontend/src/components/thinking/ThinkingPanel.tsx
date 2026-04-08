import { ChevronRight } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

interface ThinkingPanelProps {
  trace: string;
  streaming?: boolean;
}

export function ThinkingPanel({ trace, streaming = false }: ThinkingPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);
  const lastExpandedRef = useRef(false);
  const lastStreamingRef = useRef(streaming);

  useEffect(() => {
    if (lastStreamingRef.current && !streaming) {
      setExpanded(false);
    }
    lastStreamingRef.current = streaming;
  }, [streaming]);

  useEffect(() => {
    const scrollContainer = scrollRef.current;
    if (!expanded || !scrollContainer) {
      return;
    }

    const activeContainer = scrollContainer;

    function handleScroll() {
      const distanceToBottom =
        activeContainer.scrollHeight - activeContainer.scrollTop - activeContainer.clientHeight;
      stickToBottomRef.current = distanceToBottom <= 24;
    }

    handleScroll();
    activeContainer.addEventListener("scroll", handleScroll);
    return () => activeContainer.removeEventListener("scroll", handleScroll);
  }, [expanded]);

  useLayoutEffect(() => {
    const scrollContainer = scrollRef.current;
    if (!expanded || !scrollContainer) {
      lastExpandedRef.current = expanded;
      return;
    }

    const expandedJustOpened = !lastExpandedRef.current;
    lastExpandedRef.current = expanded;

    if (!expandedJustOpened && !stickToBottomRef.current) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      scrollContainer.scrollTop = scrollContainer.scrollHeight;
      stickToBottomRef.current = true;
    });

    return () => window.cancelAnimationFrame(frame);
  }, [expanded, trace]);

  return (
    <div className="mb-3 w-full min-w-0">
      <button
        aria-expanded={expanded}
        className="inline-flex min-h-[34px] max-w-full items-center gap-2.5 py-[2px] text-app-muted/80 transition hover:text-app-muted"
        onClick={() => setExpanded((current) => !current)}
        type="button"
      >
        <span
          className={
            streaming
              ? "app-streaming-label text-[15px] italic tracking-[0.01em]"
              : "text-[15px] italic tracking-[0.01em] text-app-muted/80"
          }
        >
          Thinking
        </span>
        {streaming ? (
          <span aria-hidden="true" className="inline-flex items-center gap-1.25 self-center">
            <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.15s_infinite]" />
            <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.3s_infinite]" />
            <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.45s_infinite]" />
          </span>
        ) : null}
        <ChevronRight className={`size-4 shrink-0 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`} />
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
            <div className="whitespace-pre-wrap break-words">{trace}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
