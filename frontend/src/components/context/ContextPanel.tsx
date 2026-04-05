import { ChevronRight, Database, History, LibraryBig, ScrollText } from "lucide-react";
import { useMemo, useState } from "react";

import type { MessageContext, MessageContextSection } from "../../types";

interface ContextPanelProps {
  context: MessageContext;
}

function sectionIcon(kind: MessageContextSection["kind"]) {
  if (kind === "summary") {
    return <ScrollText className="size-4" />;
  }
  if (kind === "history") {
    return <History className="size-4" />;
  }
  if (kind === "memory") {
    return <Database className="size-4" />;
  }
  return <LibraryBig className="size-4" />;
}

function sectionMeta(section: MessageContextSection) {
  return section.item_count > 0 ? `${section.item_count}` : null;
}

export function ContextPanel({ context }: ContextPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const visibleSections = useMemo(
    () => context.sections.filter((section) => section.body.trim().length > 0),
    [context.sections],
  );

  if (visibleSections.length === 0) {
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
        <span>Context</span>
        <span className="text-app-muted/70">
          {context.strategy}
          {context.strategy ? " · " : ""}
          {context.older_message_count > 0 ? `${context.older_message_count} older` : "recent only"}
          {context.memory_count > 0 ? ` · ${context.memory_count} memories` : ""}
          {context.source_count > 0 ? ` · ${context.source_count} sources` : ""}
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
            <div className="space-y-3">
              {visibleSections.map((section) => {
                const meta = sectionMeta(section);
                return (
                  <section key={`${section.kind}-${section.title}`}>
                    <div className="flex items-center gap-2 text-[13px] font-medium text-app-muted">
                      {sectionIcon(section.kind)}
                      <span>{section.title}</span>
                      {meta ? <span className="text-app-muted/65">{meta}</span> : null}
                    </div>
                    <div className="mt-2 whitespace-pre-wrap break-words border-l border-app-border pl-3 text-[13px] leading-6 text-app-text/88">
                      {section.body}
                    </div>
                  </section>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
