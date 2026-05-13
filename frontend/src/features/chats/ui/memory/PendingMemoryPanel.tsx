import { Brain, Check, Pencil, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import type { MemoryCandidateUpdatePayload, MemoryItem, MemoryKind, MemoryScope } from "../../../../types";

const MEMORY_KIND_LABELS: Record<MemoryKind, string> = {
  profile: "画像",
  preference: "偏好",
  goal: "目标",
  project: "项目",
  fact: "事实",
  constraint: "约束",
};

const EDITABLE_KINDS: MemoryKind[] = ["profile", "preference", "goal", "project", "fact", "constraint"];
const EDITABLE_SCOPES: Array<Exclude<MemoryScope, "working">> = ["conversation", "global"];

type PendingMemoryDraft = MemoryCandidateUpdatePayload & {
  tagsText: string;
};

interface PendingMemoryPanelProps {
  memories: MemoryItem[];
  onConfirm?: (memoryId: number, payload?: MemoryCandidateUpdatePayload) => Promise<void> | void;
  onReject?: (memoryId: number) => Promise<void> | void;
}

function createDraft(memory: MemoryItem): PendingMemoryDraft {
  return {
    scope: memory.scope === "global" ? "global" : "conversation",
    kind: memory.kind,
    title: memory.title,
    detail: memory.detail,
    tags: [...memory.tags],
    tagsText: memory.tags.join(", "),
  };
}

function normalizeTags(value: string) {
  const tags: string[] = [];
  value
    .split(/[,，]/)
    .map((tag) => tag.trim())
    .filter(Boolean)
    .forEach((tag) => {
      if (!tags.includes(tag)) {
        tags.push(tag);
      }
    });
  return tags;
}

function toPayload(draft: PendingMemoryDraft): MemoryCandidateUpdatePayload {
  return {
    scope: draft.scope,
    kind: draft.kind,
    title: draft.title.trim(),
    detail: draft.detail.trim(),
    tags: normalizeTags(draft.tagsText),
  };
}

function ActionButton({
  children,
  disabled,
  onClick,
  tone,
}: {
  children: ReactNode;
  disabled?: boolean;
  onClick: () => void;
  tone: "reject" | "confirm";
}) {
  const toneClass =
    tone === "confirm"
      ? "border-[#9bc9aa] bg-[#eef8f1] text-[#28723b] hover:border-[#78b88a] hover:bg-[#e5f4e9]"
      : "border-app-border bg-white text-app-muted hover:border-[#d7c2bc] hover:bg-[#fbf3f1] hover:text-[#8d3c33]";
  return (
    <button
      className={`flex min-h-11 min-w-0 items-center justify-center gap-2 rounded-[8px] border px-3 text-[14px] font-medium transition disabled:cursor-not-allowed disabled:opacity-55 ${toneClass}`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}

function PendingMemoryItem({
  memory,
  onConfirm,
  onReject,
}: {
  memory: MemoryItem;
  onConfirm?: (memoryId: number, payload?: MemoryCandidateUpdatePayload) => Promise<void> | void;
  onReject?: (memoryId: number) => Promise<void> | void;
}) {
  const [draft, setDraft] = useState(() => createDraft(memory));
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState<"confirm" | "reject" | null>(null);
  const titleIsEmpty = draft.title.trim().length === 0;

  useEffect(() => {
    setDraft(createDraft(memory));
    setEditing(false);
    setSaving(null);
  }, [memory]);

  async function handleConfirm() {
    if (!onConfirm || titleIsEmpty) {
      return;
    }
    setSaving("confirm");
    try {
      await onConfirm(memory.id, editing ? toPayload(draft) : undefined);
    } finally {
      setSaving(null);
    }
  }

  async function handleReject() {
    if (!onReject) {
      return;
    }
    setSaving("reject");
    try {
      await onReject(memory.id);
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="grid gap-2 md:grid-cols-[112px_minmax(0,1fr)_112px]">
      <ActionButton disabled={saving !== null} onClick={() => void handleReject()} tone="reject">
        <X className="size-4 shrink-0" />
        <span>不要记</span>
      </ActionButton>

      <div className="min-w-0 rounded-[8px] border border-app-border bg-white px-3 py-3">
        <div className="mb-2 flex min-w-0 items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <span className="rounded-[6px] bg-app-panel-soft px-2 py-0.5 text-[12px] font-medium text-app-muted">
              {MEMORY_KIND_LABELS[memory.kind]}
            </span>
            <span className="min-w-0 truncate text-[12px] text-app-muted">
              {memory.scope === "global" ? "长期记忆" : "当前对话"}
            </span>
          </div>
          <button
            className="flex size-8 shrink-0 items-center justify-center rounded-[8px] text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
            onClick={() => setEditing((value) => !value)}
            title={editing ? "取消编辑" : "编辑候选记忆"}
            type="button"
          >
            <Pencil className="size-4" />
          </button>
        </div>

        {editing ? (
          <div className="space-y-2">
            <div className="grid gap-2 sm:grid-cols-2">
              <select
                className="h-9 rounded-[8px] border border-app-border bg-white px-2 text-[13px] text-app-text outline-none focus:border-app-border-strong"
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    scope: event.target.value as Exclude<MemoryScope, "working">,
                  }))
                }
                value={draft.scope}
              >
                {EDITABLE_SCOPES.map((scope) => (
                  <option key={scope} value={scope}>
                    {scope === "global" ? "长期记忆" : "当前对话"}
                  </option>
                ))}
              </select>
              <select
                className="h-9 rounded-[8px] border border-app-border bg-white px-2 text-[13px] text-app-text outline-none focus:border-app-border-strong"
                onChange={(event) =>
                  setDraft((current) => ({ ...current, kind: event.target.value as MemoryKind }))
                }
                value={draft.kind}
              >
                {EDITABLE_KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {MEMORY_KIND_LABELS[kind]}
                  </option>
                ))}
              </select>
            </div>
            <input
              className="h-9 w-full rounded-[8px] border border-app-border bg-white px-2 text-[13px] text-app-text outline-none focus:border-app-border-strong"
              onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
              placeholder="标题"
              value={draft.title}
            />
            <textarea
              className="min-h-[76px] w-full resize-y rounded-[8px] border border-app-border bg-white px-2 py-2 text-[13px] leading-5 text-app-text outline-none focus:border-app-border-strong"
              onChange={(event) => setDraft((current) => ({ ...current, detail: event.target.value }))}
              placeholder="细节"
              value={draft.detail}
            />
            <input
              className="h-9 w-full rounded-[8px] border border-app-border bg-white px-2 text-[13px] text-app-text outline-none focus:border-app-border-strong"
              onChange={(event) => setDraft((current) => ({ ...current, tagsText: event.target.value }))}
              placeholder="标签，用逗号分隔"
              value={draft.tagsText}
            />
          </div>
        ) : (
          <div>
            <div className="break-words text-[14px] font-medium leading-6 text-app-text">{memory.title}</div>
            {memory.detail ? (
              <div className="mt-1 whitespace-pre-wrap break-words text-[13px] leading-6 text-app-muted">
                {memory.detail}
              </div>
            ) : null}
            {memory.tags.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {memory.tags.map((tag) => (
                  <span className="rounded-[6px] bg-app-panel-soft px-2 py-0.5 text-[12px] text-app-muted" key={tag}>
                    {tag}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        )}
      </div>

      <ActionButton disabled={saving !== null || titleIsEmpty} onClick={() => void handleConfirm()} tone="confirm">
        <span>记住</span>
        <Check className="size-4 shrink-0" />
      </ActionButton>
    </div>
  );
}

export function PendingMemoryPanel({ memories, onConfirm, onReject }: PendingMemoryPanelProps) {
  const pendingMemories = memories.filter((memory) => memory.confidence_state === "pending");
  if (pendingMemories.length === 0) {
    return null;
  }

  return (
    <section className="mt-4 rounded-[12px] border border-app-border bg-app-panel-soft p-3">
      <div className="mb-3 flex items-center gap-2 text-[13px] font-medium text-app-muted">
        <Brain className="size-4" />
        <span>候选记忆</span>
      </div>
      <div className="space-y-2">
        {pendingMemories.map((memory) => (
          <PendingMemoryItem
            key={memory.id}
            memory={memory}
            onConfirm={onConfirm}
            onReject={onReject}
          />
        ))}
      </div>
    </section>
  );
}
