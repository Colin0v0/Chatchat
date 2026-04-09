import { ChevronRight, ScrollText } from "lucide-react";
import { useMemo, useState } from "react";

import type { MessageContext, MessageContextSection } from "../../types";

interface ContextPanelProps {
  context: MessageContext;
}

export function ContextPanel({ context }: ContextPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const summarySection = useMemo(
    () => context.sections.find((section) => section.body.trim().length > 0) ?? null,
    [context.sections],
  );

  if (!summarySection) {
    return null;
  }

  return (
    <div className="mt-4">
      <button
        aria-expanded={expanded}
        className="inline-flex items-center gap-2 rounded-lg py-1 text-[13px] text-app-muted/85 transition hover:text-app-text"
        onClick={() => setExpanded((value) => !value)}
        type="button"
      >
        <span>上下文</span>
        <span className="text-app-muted/70">
          {`已截取最近 ${Math.max(1, context.recent_message_count)} 轮对话`}
          {context.older_message_count > 0 ? `，更早 ${context.older_message_count} 轮已压缩` : ""}
        </span>
        <ChevronRight className={`size-4 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`} />
      </button>

      <div
        className={`grid transition-[grid-template-rows,opacity,margin] duration-200 ${
          expanded ? "mt-3 grid-rows-[1fr] opacity-100" : "mt-0 grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="overflow-hidden">
          <div className="rounded-2xl border border-app-border bg-app-panel-strong/70 px-4 py-4">
            <section>
              <div className="flex items-center gap-2 text-[13px] font-medium text-app-muted">
                <ScrollText className="size-4" />
                <span>中文总结</span>
              </div>
              <div className="mt-2 whitespace-pre-wrap break-words border-l border-app-border pl-3 text-[13px] leading-6 text-app-text/88">
                {summarySection.body}
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
}
