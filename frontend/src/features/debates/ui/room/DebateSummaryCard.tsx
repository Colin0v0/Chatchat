import { ChevronDown, Sparkles } from "lucide-react";

import { MarkdownMessage } from "../../../chats/ui/markdown/MarkdownMessage";

export function DebateSummaryCard({
  expanded,
  onToggle,
  summary,
}: {
  expanded: boolean;
  onToggle: () => void;
  summary: string;
}) {
  if (!summary) {
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
          结果总结
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
          <div className="prose-debate px-6 py-3 text-[14px] leading-7 text-app-text">
            <MarkdownMessage content={summary} />
          </div>
        </div>
      </div>
    </div>
  );
}
