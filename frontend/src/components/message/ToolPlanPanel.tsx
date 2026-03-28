import { ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { ToolPlan } from "../../types";

interface ToolPlanPanelProps {
  plan: ToolPlan;
}

function toToolLabel(tool: ToolPlan["tool"]) {
  if (tool === "rag_search") {
    return "RAG";
  }
  if (tool === "web_search") {
    return "Web";
  }
  if (tool === "both") {
    return "RAG + Web";
  }
  return "Direct answer";
}

export function ToolPlanPanel({ plan }: ToolPlanPanelProps) {
  const [expanded, setExpanded] = useState(true);
  const summary = useMemo(() => toToolLabel(plan.tool), [plan.tool]);

  useEffect(() => {
    setExpanded(true);
  }, [plan.reason, plan.rag_query, plan.run_rag, plan.run_web, plan.tool, plan.web_query]);

  return (
    <div className="mb-3">
      <button
        aria-expanded={expanded}
        className="inline-flex items-center gap-2 leading-none text-app-muted/80 transition hover:text-app-muted"
        onClick={() => setExpanded((current) => !current)}
        type="button"
      >
        <span className="text-[14px] tracking-[-0.01em]">Tool choice</span>
        <span className="text-[13px] text-app-muted/70">{summary}</span>
        <ChevronRight className={`size-4 transition-transform duration-200 ${expanded ? "rotate-90" : ""}`} />
      </button>

      <div
        className={`grid transition-[grid-template-rows,opacity,margin] duration-200 ${
          expanded ? "mt-3 grid-rows-[1fr] opacity-100" : "mt-0 grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="overflow-hidden">
          <div className="space-y-1.5 border-l border-app-border pl-4 text-[13px] leading-6 text-app-muted/78">
            <div>
              <span className="text-app-muted/60">Mode:</span> {summary}
            </div>
            <div>
              <span className="text-app-muted/60">Reason:</span> {plan.reason}
            </div>
            {plan.rag_query ? (
              <div>
                <span className="text-app-muted/60">RAG query:</span> {plan.rag_query}
              </div>
            ) : null}
            {plan.web_query ? (
              <div>
                <span className="text-app-muted/60">Web query:</span> {plan.web_query}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
