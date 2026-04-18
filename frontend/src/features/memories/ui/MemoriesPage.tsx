import { Check, ChevronDown, Pin, PinOff, Plus, RefreshCw, Trash2 } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import type { MemoryDocument, MemoryItem } from "../../../types";
import { WorkspacePage } from "../../../shared/ui/WorkspacePage";

type MemoryEditorState = {
  id: number | null;
  scope: "global" | "conversation";
  kind: "profile" | "preference" | "goal" | "project" | "fact" | "constraint";
  title: string;
  detail: string;
  tagsText: string;
  confidenceText: string;
  pinned: boolean;
  active: boolean;
  conversation_id: number | null;
} | null;

const MEMORY_KIND_LABELS: Record<MemoryItem["kind"], string> = {
  profile: "身份",
  preference: "偏好",
  goal: "目标",
  project: "项目",
  fact: "事实",
  constraint: "约束",
};

const MEMORY_SOURCE_LABELS: Record<string, string> = {
  auto: "系统识别",
  manual: "手动添加",
  promoted: "主动记住",
};

const DOCUMENT_LABELS: Record<MemoryDocument["doc_type"], string> = {
  user_profile: "用户画像文档",
  workspace_profile: "工作区文档",
  conversation_brief: "当前会话文档",
};

type SelectOption<T extends string> = {
  value: T;
  label: string;
  disabled?: boolean;
};

function StatChip({ children }: { children: string }) {
  return (
    <span className="rounded-full border border-app-border bg-app-panel-strong px-3 py-1.5 text-[13px] text-app-muted">
      {children}
    </span>
  );
}

function EmptyState({ children }: { children: string }) {
  return (
    <div className="rounded-xl border border-dashed border-app-border bg-app-panel-strong px-4 py-8 text-[14px] text-app-muted">
      {children}
    </div>
  );
}

function FormLabel({ children }: { children: ReactNode }) {
  return (
    <span className="text-[12px] font-semibold tracking-[0.14em] text-app-muted uppercase">{children}</span>
  );
}

function CustomSelect<T extends string>({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (value: T) => void;
  options: SelectOption<T>[];
  value: T;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const listboxId = useId();
  const selected = options.find((option) => option.value === value) ?? options[0];

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  return (
    <div className="flex flex-col gap-2" ref={rootRef}>
      <FormLabel>{label}</FormLabel>
      <div className="relative">
        <button
          aria-controls={listboxId}
          aria-expanded={open}
          className="flex w-full items-center justify-between rounded-xl border border-app-border bg-app-panel px-4 py-3 text-left transition hover:border-app-border-strong hover:bg-app-panel-soft"
          onClick={() => setOpen((current) => !current)}
          type="button"
        >
          <span className="text-[15px] font-medium text-app-text">{selected?.label ?? ""}</span>
          <ChevronDown className={`size-4 text-app-muted transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
        </button>

        {open ? (
          <div
            className="absolute left-0 right-0 top-[calc(100%+8px)] z-20 overflow-hidden rounded-xl border border-app-border bg-app-panel-strong p-2 shadow-[0_18px_48px_rgba(34,24,16,0.14)]"
            id={listboxId}
            role="listbox"
          >
            <div className="flex flex-col gap-1">
              {options.map((option) => {
                const selectedOption = option.value === value;
                return (
                  <button
                    aria-selected={selectedOption}
                    className={[
                      "flex items-center justify-between rounded-lg px-3 py-2.5 text-left text-[15px] transition",
                      option.disabled
                        ? "cursor-not-allowed opacity-45"
                        : selectedOption
                          ? "bg-app-accent text-white"
                          : "text-app-text hover:bg-app-panel",
                    ].join(" ")}
                    disabled={option.disabled}
                    key={option.value}
                    onClick={() => {
                      if (option.disabled) {
                        return;
                      }
                      onChange(option.value);
                      setOpen(false);
                    }}
                    role="option"
                    type="button"
                  >
                    <span>{option.label}</span>
                    {selectedOption ? <Check className="size-4" /> : null}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "未记录";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "未记录";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatSourceLabel(value: string): string {
  return MEMORY_SOURCE_LABELS[value] ?? value;
}

function MemoryCard({
  memory,
  onDelete,
  onEdit,
}: {
  memory: MemoryItem;
  onDelete?: (memoryId: number) => void;
  onEdit?: (memory: MemoryItem) => void;
}) {
  return (
    <div className="rounded-xl border border-app-border bg-app-panel-strong p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-app-border px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-muted">
              {MEMORY_KIND_LABELS[memory.kind]}
            </span>
            {memory.pinned ? (
              <span className="rounded-full bg-app-accent-soft px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-accent-strong">
                固定注入
              </span>
            ) : null}
          </div>
          <div className="mt-3 text-[16px] font-semibold tracking-[-0.02em] text-app-text">{memory.title}</div>
          {memory.detail ? <div className="mt-2 text-[14px] leading-6 text-app-muted">{memory.detail}</div> : null}
          {memory.tags.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {memory.tags.map((tag) => (
                <span className="rounded-full border border-app-border bg-app-panel px-2.5 py-1 text-[12px] text-app-muted" key={tag}>
                  #{tag}
                </span>
              ))}
            </div>
          ) : null}
        </div>

        <div className="ml-auto flex w-full shrink-0 items-center justify-end gap-2 sm:w-auto">
          {onEdit ? (
            <button
              className="flex h-9 items-center rounded-lg border border-app-border bg-app-panel px-3 text-[13px] text-app-muted transition hover:text-app-text"
              onClick={() => onEdit(memory)}
              type="button"
            >
              编辑
            </button>
          ) : null}
          {onDelete ? (
            <button
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-app-border bg-app-panel text-app-muted transition hover:text-app-text"
              onClick={() => onDelete(memory.id)}
              type="button"
            >
              <Trash2 className="size-4" />
            </button>
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 text-[12px] text-app-muted">
        <span>置信度 {Math.round(memory.confidence * 100)}%</span>
        <span>{memory.pinned ? <Pin className="inline size-3.5" /> : <PinOff className="inline size-3.5" />}</span>
        <span>来源 {formatSourceLabel(memory.source_type)}</span>
        <span>最近使用 {formatTimestamp(memory.last_used_at)}</span>
        {memory.expires_at ? <span>过期 {formatTimestamp(memory.expires_at)}</span> : null}
      </div>
    </div>
  );
}

function DocumentCard({ document }: { document: MemoryDocument }) {
  return (
    <div className="rounded-xl border border-app-border bg-app-panel-strong p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 text-[15px] font-semibold tracking-[-0.02em] text-app-text">{DOCUMENT_LABELS[document.doc_type]}</div>
        <div className="w-full text-[12px] text-app-muted sm:w-auto sm:text-right">{formatTimestamp(document.updated_at)}</div>
      </div>
      <div className="mt-3 whitespace-pre-wrap text-[14px] leading-6 text-app-muted">{document.content}</div>
    </div>
  );
}

function CandidateMemoryCard({
  isSaving,
  memory,
  onDismiss,
  onPromoteGlobal,
}: {
  isSaving?: boolean;
  memory: MemoryItem;
  onDismiss: (memoryId: number) => void;
  onPromoteGlobal: (memoryId: number) => void;
}) {
  return (
    <div className="rounded-xl border border-app-border bg-app-panel-strong p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-app-accent-soft px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-accent-strong">
              系统候选
            </span>
            <span className="rounded-full border border-app-border px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-muted">
              {MEMORY_KIND_LABELS[memory.kind]}
            </span>
          </div>
          <div className="mt-3 text-[16px] font-semibold tracking-[-0.02em] text-app-text">{memory.title}</div>
          {memory.detail ? <div className="mt-2 text-[14px] leading-6 text-app-muted">{memory.detail}</div> : null}
          {memory.tags.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {memory.tags.map((tag) => (
                <span className="rounded-full border border-app-border bg-app-panel px-2.5 py-1 text-[12px] text-app-muted" key={tag}>
                  #{tag}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          className="rounded-lg bg-app-accent-soft px-3 py-2 text-[13px] font-medium text-app-accent-strong transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-45"
          disabled={isSaving}
          onClick={() => onPromoteGlobal(memory.id)}
          type="button"
        >
          加入全局记忆
        </button>
        <button
          className="rounded-lg border border-app-border px-3 py-2 text-[13px] font-medium text-app-muted transition hover:bg-app-panel hover:text-app-text disabled:cursor-not-allowed disabled:opacity-45"
          disabled={isSaving}
          onClick={() => onDismiss(memory.id)}
          type="button"
        >
          忽略
        </button>
      </div>

      <div className="mt-3 text-[12px] leading-5 text-app-muted">
        系统会先把它当作候选，只有你确认之后，才会进入长期的全局记忆。
      </div>
    </div>
  );
}

export function MemoriesPage({
  activeConversationId: _activeConversationId,
  activeConversationTitle: _activeConversationTitle,
  memories,
}: {
  activeConversationId: number | null;
  activeConversationTitle: string;
  memories: {
    collection: {
      documents: MemoryDocument[];
      active_items: {
        global_items: MemoryItem[];
        conversation_items: MemoryItem[];
        working_items: MemoryItem[];
      };
      candidate_items: {
        global_items: MemoryItem[];
        conversation_items: MemoryItem[];
        working_items: MemoryItem[];
      };
    };
    editor: MemoryEditorState;
    error: string | null;
    hasMemories: boolean;
    isLoading: boolean;
    isSaving: boolean;
    onCancelEditing: () => void;
    onChangeEditor: (patch: Record<string, unknown>) => void;
    onCreateGlobalMemory: () => void;
    onDeleteMemory: (memoryId: number) => void;
    onDismissCandidate: (memoryId: number) => void;
    onEditMemory: (memory: MemoryItem) => void;
    onPromoteCandidate: (memoryId: number, scope: "global") => void;
    onRefresh: () => void;
    onSaveEditing: () => void;
  };
}) {
  const activeGlobal = memories.collection.active_items.global_items;
  const globalCandidates = memories.collection.candidate_items.global_items;
  const conversationCandidates = memories.collection.candidate_items.conversation_items;
  const candidateItems = [...globalCandidates, ...conversationCandidates];
  const visibleHasMemories =
    memories.collection.documents.length > 0 || activeGlobal.length > 0 || candidateItems.length > 0 || memories.editor != null;
  const kindOptions: SelectOption<NonNullable<MemoryEditorState>["kind"]>[] = [
    { value: "profile", label: "身份" },
    { value: "preference", label: "偏好" },
    { value: "goal", label: "目标" },
    { value: "project", label: "项目" },
    { value: "fact", label: "事实" },
    { value: "constraint", label: "约束" },
  ];

  return (
    <WorkspacePage
      headerPlacement="content"
      maxWidthClassName="max-w-[1320px]"
      actions={
        <div className="grid w-full grid-cols-2 gap-3 sm:flex sm:w-auto sm:flex-wrap sm:justify-end">
          <button
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-app-border bg-app-panel-strong px-4 py-2.5 text-[14px] font-medium text-app-text transition hover:bg-app-panel-soft sm:w-auto"
            onClick={memories.onCreateGlobalMemory}
            type="button"
          >
            <Plus className="size-4" />
            新建全局记忆
          </button>
          <button
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-app-border bg-app-panel px-4 py-2.5 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text sm:w-auto"
            onClick={memories.onRefresh}
            type="button"
          >
            <RefreshCw className={`size-4 ${memories.isLoading ? "animate-spin" : ""}`} />
            刷新
          </button>
        </div>
      }
      title="Memories"
    >
      <div className="flex flex-wrap gap-2">
        <StatChip>{`全局记忆 ${activeGlobal.length}`}</StatChip>
        <StatChip>{`全局候选 ${candidateItems.length}`}</StatChip>
        <StatChip>{`记忆文档 ${memories.collection.documents.length}`}</StatChip>
      </div>

      {memories.error ? <div className="text-[13px] leading-6 text-[#9d3d32]">{memories.error}</div> : null}

      {!memories.isLoading && !visibleHasMemories ? (
        <div className="rounded-[20px] border border-dashed border-app-border bg-app-panel-strong px-5 py-6">
          <div className="text-[16px] font-semibold tracking-[-0.02em] text-app-text">记忆空间还是空的</div>
          <div className="mt-2 text-[14px] leading-7 text-app-muted">
            可以先新建全局记忆。系统后续自动识别出来的长期信息，也会先以候选的形式出现在这里等你确认。
          </div>
        </div>
      ) : null}

      {memories.editor ? (
        <div className="rounded-[20px] border border-app-border bg-app-panel-strong p-3">
          <div className="flex items-center justify-between gap-4">
            <div className="text-[16px] font-semibold tracking-[-0.02em] text-app-text">
              {memories.editor.id == null ? "新建记忆" : "编辑记忆"}
            </div>
            <div className="flex gap-2">
              <button
                className="rounded-lg px-4 py-2.5 text-[14px] font-medium text-app-muted transition hover:bg-app-panel hover:text-app-text"
                onClick={memories.onCancelEditing}
                type="button"
              >
                取消
              </button>
              <button
                className="rounded-lg bg-app-accent-soft px-4 py-2.5 text-[14px] font-medium text-app-accent-strong transition hover:bg-app-panel disabled:cursor-not-allowed disabled:opacity-60"
                disabled={memories.isSaving}
                onClick={memories.onSaveEditing}
                type="button"
              >
                {memories.isSaving ? "保存中..." : "保存"}
              </button>
            </div>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <CustomSelect
              label="类型"
              onChange={(kind) => memories.onChangeEditor({ kind })}
              options={kindOptions}
              value={memories.editor.kind}
            />

            <label className="md:col-span-2 flex flex-col gap-2">
              <FormLabel>标题</FormLabel>
              <input
                className="rounded-xl border border-app-border bg-app-panel px-4 py-3 text-[14px] text-app-text"
                onChange={(event) => memories.onChangeEditor({ title: event.target.value })}
                placeholder="一条记忆只写一个稳定事实"
                value={memories.editor.title}
              />
            </label>

            <label className="md:col-span-2 flex flex-col gap-2">
              <FormLabel>详情</FormLabel>
              <textarea
                className="min-h-[120px] rounded-xl border border-app-border bg-app-panel px-4 py-3 text-[14px] leading-6 text-app-text"
                onChange={(event) => memories.onChangeEditor({ detail: event.target.value })}
                placeholder="补充细节、边界条件或适用范围"
                value={memories.editor.detail}
              />
            </label>

            <label className="flex flex-col gap-2">
              <FormLabel>标签</FormLabel>
              <input
                className="rounded-xl border border-app-border bg-app-panel px-4 py-3 text-[14px] text-app-text"
                onChange={(event) => memories.onChangeEditor({ tagsText: event.target.value })}
                placeholder="写作, 编程, 产品"
                value={memories.editor.tagsText}
              />
            </label>

            <label className="flex flex-col gap-2">
              <FormLabel>置信度</FormLabel>
              <input
                className="rounded-xl border border-app-border bg-app-panel px-4 py-3 text-[14px] text-app-text"
                max="1"
                min="0"
                onChange={(event) => memories.onChangeEditor({ confidenceText: event.target.value })}
                step="0.05"
                type="number"
                value={memories.editor.confidenceText}
              />
            </label>
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <label className="inline-flex items-center gap-2 rounded-full border border-app-border bg-app-panel px-3 py-2 text-[13px] text-app-muted">
              <input
                checked={memories.editor.pinned}
                onChange={(event) => memories.onChangeEditor({ pinned: event.target.checked })}
                type="checkbox"
              />
              固定注入
            </label>
            <label className="inline-flex items-center gap-2 rounded-full border border-app-border bg-app-panel px-3 py-2 text-[13px] text-app-muted">
              <input
                checked={memories.editor.active}
                onChange={(event) => memories.onChangeEditor({ active: event.target.checked })}
                type="checkbox"
              />
              启用
            </label>
          </div>
        </div>
      ) : null}

      <div>
        <div className="mb-3 text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">记忆文档</div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4">
          {memories.collection.documents.map((document) => (
            <DocumentCard document={document} key={document.id} />
          ))}
          {memories.collection.documents.length === 0 ? <EmptyState>还没有文档，系统会在全局记忆稳定后自动整理。</EmptyState> : null}
        </div>
      </div>

      <div>
        <div>
          <div className="mb-3 text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">全局记忆</div>
          <div className="flex flex-col gap-4">
            {activeGlobal.map((memory) => (
              <MemoryCard key={memory.id} memory={memory} onDelete={memories.onDeleteMemory} onEdit={memories.onEditMemory} />
            ))}
            {activeGlobal.length === 0 ? <EmptyState>还没有全局记忆。</EmptyState> : null}
          </div>
        </div>
      </div>

      <div>
        <div>
          <div className="mb-3 text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">全局候选</div>
          <div className="flex flex-col gap-4">
            {candidateItems.map((memory) => (
              <CandidateMemoryCard
                isSaving={memories.isSaving}
                key={memory.id}
                memory={memory}
                onDismiss={memories.onDismissCandidate}
                onPromoteGlobal={(memoryId) => memories.onPromoteCandidate(memoryId, "global")}
              />
            ))}
            {candidateItems.length === 0 ? <EmptyState>还没有系统自动识别出的候选。</EmptyState> : null}
          </div>
        </div>
      </div>
    </WorkspacePage>
  );
}
