import { Pin, PinOff, Pencil, Trash2 } from "lucide-react";

import type { MemoryDocument, MemoryItem } from "../../../types";
import {
  DOCUMENT_LABELS,
  formatMemoryConfidence,
  formatMemorySource,
  formatMemoryTimestamp,
  MEMORY_CONFIDENCE_STATE_LABELS,
  MEMORY_KIND_LABELS,
  MEMORY_SCOPE_LABELS,
} from "./memoryPresentation";

interface MemoryCardProps {
  memory: MemoryItem;
  onDelete?: (memoryId: number) => void;
  onEdit?: (memory: MemoryItem) => void;
}

function MemoryBadge({ children, tone = "neutral" }: { children: string; tone?: "neutral" | "accent" }) {
  return (
    <span
      className={[
        "inline-flex h-6 items-center rounded-[8px] px-2 text-[12px] font-medium",
        tone === "accent"
          ? "bg-app-accent-soft text-app-accent-strong"
          : "border border-app-border bg-app-panel text-app-muted",
      ].join(" ")}
    >
      {children}
    </span>
  );
}

function MemoryMeta({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex min-w-0 items-center gap-1 text-[12px] leading-5 text-app-muted">
      <span className="shrink-0">{label}</span>
      <span className="min-w-0 truncate text-app-text/80">{value}</span>
    </span>
  );
}

export function MemoryCard({ memory, onDelete, onEdit }: MemoryCardProps) {
  const editable = memory.scope !== "working" && onEdit;

  return (
    <article className="rounded-[8px] border border-app-border bg-app-panel-strong p-4">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <MemoryBadge>{MEMORY_KIND_LABELS[memory.kind]}</MemoryBadge>
            <MemoryBadge>{MEMORY_SCOPE_LABELS[memory.scope]}</MemoryBadge>
            <MemoryBadge tone={memory.confidence_state === "confirmed" ? "accent" : "neutral"}>
              {MEMORY_CONFIDENCE_STATE_LABELS[memory.confidence_state]}
            </MemoryBadge>
            {memory.pinned ? <MemoryBadge tone="accent">固定注入</MemoryBadge> : null}
          </div>

          <h3 className="mt-3 break-words text-[16px] font-semibold leading-6 text-app-text">{memory.title}</h3>
          {memory.detail ? <p className="mt-2 whitespace-pre-wrap break-words text-[14px] leading-6 text-app-muted">{memory.detail}</p> : null}

          {memory.tags.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {memory.tags.map((tag) => (
                <span className="rounded-[8px] border border-app-border bg-app-panel px-2 py-1 text-[12px] leading-4 text-app-muted" key={tag}>
                  #{tag}
                </span>
              ))}
            </div>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-1">
          {editable ? (
            <button
              className="inline-flex h-9 items-center gap-1.5 rounded-[8px] px-2.5 text-[13px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
              onClick={() => onEdit(memory)}
              type="button"
            >
              <Pencil className="size-3.5" />
              编辑
            </button>
          ) : null}
          {onDelete ? (
            <button
              className="flex h-9 w-9 items-center justify-center rounded-[8px] text-app-muted transition hover:bg-[#fbefed] hover:text-[#9d3d32]"
              onClick={() => onDelete(memory.id)}
              title="删除"
              type="button"
            >
              <Trash2 className="size-4" />
            </button>
          ) : null}
        </div>
      </div>

      <div className="mt-4 grid gap-x-4 gap-y-1 border-t border-app-border pt-3 sm:grid-cols-2 xl:grid-cols-4">
        <MemoryMeta label="置信度" value={formatMemoryConfidence(memory.confidence)} />
        <MemoryMeta label="来源" value={formatMemorySource(memory.source_type)} />
        <MemoryMeta label="最近使用" value={formatMemoryTimestamp(memory.last_used_at)} />
        <span className="inline-flex items-center gap-1 text-[12px] leading-5 text-app-muted">
          {memory.pinned ? <Pin className="size-3.5" /> : <PinOff className="size-3.5" />}
          {memory.active ? "启用" : "停用"}
        </span>
        {memory.expires_at ? <MemoryMeta label="过期" value={formatMemoryTimestamp(memory.expires_at)} /> : null}
      </div>
    </article>
  );
}

export function MemoryDocumentCard({ document }: { document: MemoryDocument }) {
  return (
    <article className="rounded-[8px] border border-app-border bg-app-panel-strong p-4">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0 text-[15px] font-semibold leading-6 text-app-text">{DOCUMENT_LABELS[document.doc_type]}</div>
        <div className="shrink-0 text-[12px] leading-5 text-app-muted">{formatMemoryTimestamp(document.updated_at)}</div>
      </div>
      <div className="app-scrollbar mt-3 max-h-[220px] overflow-y-auto whitespace-pre-wrap break-words text-[13px] leading-6 text-app-muted">
        {document.content}
      </div>
    </article>
  );
}

export function MemoryEmptyState({ children }: { children: string }) {
  return (
    <div className="rounded-[8px] border border-dashed border-app-border bg-app-panel-strong px-4 py-8 text-[14px] leading-6 text-app-muted">
      {children}
    </div>
  );
}
