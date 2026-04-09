import {
  ArrowUpCircle,
  Check,
  ChevronDown,
  FileText,
  Pencil,
  Pin,
  PinOff,
  Plus,
  RefreshCw,
  Trash2,
  XCircle,
} from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import type { MemoryDocument, MemoryItem, RagReindexResult } from "../types";

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

interface SettingsDialogProps {
  open: boolean;
  isUpdating: boolean;
  updateError: string | null;
  updateResult: RagReindexResult | null;
  activeConversationId: number | null;
  activeConversationTitle: string;
  memories: {
    canCreateConversationMemory: boolean;
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
    onCreateConversationMemory: () => void;
    onCreateGlobalMemory: () => void;
    onDeleteMemory: (memoryId: number) => void;
    onDismissCandidate: (memoryId: number) => void;
    onEditMemory: (memory: MemoryItem) => void;
    onPromoteCandidate: (memoryId: number, scope: "global" | "conversation") => void;
    onRefresh: () => void;
    onSaveEditing: () => void;
  };
  onClose: () => void;
  onUpdateDatabase: () => void;
}

const MEMORY_KIND_LABELS: Record<MemoryItem["kind"], string> = {
  profile: "身份",
  preference: "偏好",
  goal: "目标",
  project: "项目",
  fact: "事实",
  constraint: "约束",
};

const MEMORY_SCOPE_LABELS: Record<MemoryItem["scope"], string> = {
  global: "全局",
  conversation: "会话",
  working: "工作中",
};

const MEMORY_STATUS_LABELS: Record<MemoryItem["status"], string> = {
  active: "生效中",
  candidate: "待确认",
  archived: "已归档",
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

function FormLabel({ children }: { children: string }) {
  return (
    <span className="text-[12px] font-semibold tracking-[0.14em] text-app-muted uppercase">{children}</span>
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
          <ChevronDown
            className={`size-4 text-app-muted transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          />
        </button>

        {open ? (
          <div
            className="absolute left-0 right-0 top-[calc(100%+8px)] z-50 overflow-hidden rounded-xl border border-app-border bg-app-panel-strong p-2 shadow-[0_18px_48px_rgba(34,24,16,0.14)]"
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

function SectionTitle({ icon, title, subtitle }: { icon: ReactNode; title: string; subtitle: string }) {
  return (
    <div>
      <div className="flex items-center gap-3 text-app-text">
        {icon}
        <div className="text-[18px] font-semibold tracking-[-0.02em]">{title}</div>
      </div>
      {subtitle ? <div className="mt-2 text-[14px] leading-7 text-app-muted">{subtitle}</div> : null}
    </div>
  );
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
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-app-accent-soft px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-accent-strong">
              {MEMORY_SCOPE_LABELS[memory.scope]}
            </span>
            <span className="rounded-full border border-app-border px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-muted">
              {MEMORY_KIND_LABELS[memory.kind]}
            </span>
            <span className="rounded-full border border-app-border px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-muted">
              {MEMORY_STATUS_LABELS[memory.status]}
            </span>
          </div>
          <div className="mt-3 text-[16px] font-semibold tracking-[-0.02em] text-app-text">{memory.title}</div>
          {memory.detail ? <div className="mt-2 text-[14px] leading-6 text-app-muted">{memory.detail}</div> : null}
          {memory.tags.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {memory.tags.map((tag) => (
                <span
                  className="rounded-full border border-app-border bg-app-panel px-2.5 py-1 text-[12px] text-app-muted"
                  key={tag}
                >
                  #{tag}
                </span>
              ))}
            </div>
          ) : null}
        </div>

        {onEdit || onDelete ? (
          <div className="flex shrink-0 items-center gap-2">
            {onEdit ? (
              <button
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-app-border bg-app-panel text-app-muted transition hover:text-app-text"
                onClick={() => onEdit(memory)}
                type="button"
              >
                <Pencil className="size-4" />
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
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 text-[12px] text-app-muted">
        <span>置信度 {Math.round(memory.confidence * 100)}%</span>
        <span>{memory.pinned ? <Pin className="inline size-3.5" /> : <PinOff className="inline size-3.5" />}</span>
        <span>来源 {memory.source_type}</span>
        <span>最近使用 {formatTimestamp(memory.last_used_at)}</span>
        {memory.expires_at ? <span>过期 {formatTimestamp(memory.expires_at)}</span> : null}
      </div>
    </div>
  );
}

function CandidateCard({
  memory,
  canPromoteToConversation,
  onDismiss,
  onPromote,
}: {
  memory: MemoryItem;
  canPromoteToConversation: boolean;
  onDismiss: (memoryId: number) => void;
  onPromote: (memoryId: number, scope: "global" | "conversation") => void;
}) {
  return (
    <div className="rounded-xl border border-app-border bg-app-panel-strong p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-[#efe5d5] px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-accent-strong">
              候选记忆
            </span>
            <span className="rounded-full border border-app-border px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-muted">
              {MEMORY_KIND_LABELS[memory.kind]}
            </span>
          </div>
          <div className="mt-3 text-[16px] font-semibold tracking-[-0.02em] text-app-text">{memory.title}</div>
          {memory.detail ? <div className="mt-2 text-[14px] leading-6 text-app-muted">{memory.detail}</div> : null}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {canPromoteToConversation ? (
            <button
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-app-border bg-app-panel px-3 text-[13px] font-medium text-app-text transition hover:bg-app-panel-soft"
              onClick={() => onPromote(memory.id, "conversation")}
              type="button"
            >
              <ArrowUpCircle className="size-4" />
              升级为会话
            </button>
          ) : null}
          <button
            className="inline-flex h-9 items-center gap-2 rounded-lg border border-app-border bg-app-panel px-3 text-[13px] font-medium text-app-text transition hover:bg-app-panel-soft"
            onClick={() => onPromote(memory.id, "global")}
            type="button"
          >
            <ArrowUpCircle className="size-4" />
            升级为全局
          </button>
          <button
            className="inline-flex h-9 items-center gap-2 rounded-lg border border-app-border bg-app-panel px-3 text-[13px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
            onClick={() => onDismiss(memory.id)}
            type="button"
          >
            <XCircle className="size-4" />
            忽略
          </button>
        </div>
      </div>
    </div>
  );
}

function DocumentCard({ document }: { document: MemoryDocument }) {
  return (
    <div className="rounded-xl border border-app-border bg-app-panel-strong p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-[15px] font-semibold tracking-[-0.02em] text-app-text">
          {DOCUMENT_LABELS[document.doc_type]}
        </div>
        <div className="text-[12px] text-app-muted">{formatTimestamp(document.updated_at)}</div>
      </div>
      <div className="mt-3 whitespace-pre-wrap text-[14px] leading-6 text-app-muted">{document.content}</div>
    </div>
  );
}

export function SettingsDialog({
  open,
  isUpdating,
  updateError,
  updateResult,
  activeConversationId,
  activeConversationTitle,
  memories,
  onClose,
  onUpdateDatabase,
}: SettingsDialogProps) {
  const scopeOptions: SelectOption<NonNullable<MemoryEditorState>["scope"]>[] = [
    { value: "global", label: "全局" },
    { value: "conversation", label: "会话", disabled: !memories.canCreateConversationMemory },
  ];
  const kindOptions: SelectOption<NonNullable<MemoryEditorState>["kind"]>[] = [
    { value: "profile", label: "身份" },
    { value: "preference", label: "偏好" },
    { value: "goal", label: "目标" },
    { value: "project", label: "项目" },
    { value: "fact", label: "事实" },
    { value: "constraint", label: "约束" },
  ];

  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const activeGlobal = memories.collection.active_items.global_items;
  const activeConversation = memories.collection.active_items.conversation_items;
  const activeWorking = memories.collection.active_items.working_items;
  const candidateGlobal = memories.collection.candidate_items.global_items;
  const candidateConversation = memories.collection.candidate_items.conversation_items;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(22,19,16,0.24)] px-4 py-4"
      onClick={onClose}
    >
      <div
        className="flex h-full max-h-[92vh] w-full max-w-[1160px] flex-col overflow-hidden rounded-[24px] border border-app-border bg-app-panel shadow-[0_28px_120px_rgba(34,24,16,0.22)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-app-border px-7 py-6">
          <div className="text-[30px] font-semibold tracking-[-0.04em] text-app-text">记忆管理</div>

          <button
            className="rounded-lg px-4 py-2.5 text-[15px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
            onClick={onClose}
            type="button"
          >
            关闭
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-hidden">
          <section className="app-scrollbar h-full overflow-y-auto px-7 py-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-3">
                <SectionTitle icon={<FileText className="size-5 text-app-accent-strong" />} subtitle="" title="记忆工作区" />
                <div className="flex flex-wrap gap-2 text-[13px] text-app-muted">
                  <span className="rounded-full border border-app-border bg-app-panel-strong px-3 py-1.5">
                    当前会话: {activeConversationId != null ? activeConversationTitle || `会话 #${activeConversationId}` : "未选择"}
                  </span>
                  <span className="rounded-full border border-app-border bg-app-panel-strong px-3 py-1.5">
                    候选记忆: {candidateGlobal.length + candidateConversation.length}
                  </span>
                  <span className="rounded-full border border-app-border bg-app-panel-strong px-3 py-1.5">
                    生效记忆: {activeGlobal.length + activeConversation.length + activeWorking.length}
                  </span>
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel-strong px-4 py-2.5 text-[14px] font-medium text-app-text transition hover:bg-app-panel-soft"
                  onClick={memories.onCreateGlobalMemory}
                  type="button"
                >
                  <Plus className="size-4" />
                  新建全局记忆
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel-strong px-4 py-2.5 text-[14px] font-medium text-app-text transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={!memories.canCreateConversationMemory}
                  onClick={memories.onCreateConversationMemory}
                  type="button"
                >
                  <Plus className="size-4" />
                  新建会话记忆
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel px-4 py-2.5 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
                  onClick={memories.onRefresh}
                  type="button"
                >
                  <RefreshCw className={`size-4 ${memories.isLoading ? "animate-spin" : ""}`} />
                  刷新
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel px-4 py-2.5 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={isUpdating}
                  onClick={onUpdateDatabase}
                  type="button"
                >
                  <RefreshCw className={`size-4 ${isUpdating ? "animate-spin" : ""}`} />
                  {isUpdating ? "更新中..." : "更新数据库"}
                </button>
              </div>
            </div>

            {memories.error ? <div className="mt-4 text-[13px] leading-6 text-[#9d3d32]">{memories.error}</div> : null}
            {updateError ? <div className="mt-3 text-[13px] leading-6 text-[#9d3d32]">{updateError}</div> : null}
            {updateResult ? (
              <div className="mt-4 rounded-xl border border-app-border bg-app-panel-strong px-4 py-3 text-[13px] text-app-muted">
                已更新数据库: {updateResult.indexed_files} 文件 / {updateResult.indexed_chunks} 分块 / {updateResult.failed_chunks} 失败
              </div>
            ) : null}

            {memories.editor ? (
              <div className="mt-6 rounded-[20px] border border-app-border bg-app-panel-strong p-5">
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
                    label="范围"
                    onChange={(scope) =>
                      memories.onChangeEditor({
                        scope,
                        conversation_id: scope === "conversation" ? activeConversationId : null,
                      })
                    }
                    options={scopeOptions}
                    value={memories.editor.scope}
                  />

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

            <div className="mt-6 space-y-8">
              <div>
                <div className="mb-3 text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">
                  记忆文档
                </div>
                <div className="grid gap-4 xl:grid-cols-3">
                  {memories.collection.documents.map((document) => (
                    <DocumentCard document={document} key={document.id} />
                  ))}
                  {memories.collection.documents.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-app-border bg-app-panel-strong px-4 py-8 text-[14px] text-app-muted">
                      还没有文档，系统会在记忆稳定后自动生成。
                    </div>
                  ) : null}
                </div>
              </div>

              <div>
                <div className="mb-3 text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">
                  候选记忆
                </div>
                <div className="flex flex-col gap-4">
                  {[...candidateConversation, ...candidateGlobal].map((memory) => (
                    <CandidateCard
                      canPromoteToConversation={memories.canCreateConversationMemory}
                      key={memory.id}
                      memory={memory}
                      onDismiss={memories.onDismissCandidate}
                      onPromote={memories.onPromoteCandidate}
                    />
                  ))}
                  {candidateConversation.length + candidateGlobal.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-app-border bg-app-panel-strong px-4 py-8 text-[14px] text-app-muted">
                      暂时没有待确认候选记忆。
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="grid gap-6 xl:grid-cols-3">
                <div>
                  <div className="mb-3 text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">
                    全局记忆
                  </div>
                  <div className="flex flex-col gap-4">
                    {activeGlobal.map((memory) => (
                      <MemoryCard
                        key={memory.id}
                        memory={memory}
                        onDelete={memories.onDeleteMemory}
                        onEdit={memories.onEditMemory}
                      />
                    ))}
                    {activeGlobal.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-app-border bg-app-panel-strong px-4 py-8 text-[14px] text-app-muted">
                        还没有全局记忆。
                      </div>
                    ) : null}
                  </div>
                </div>

                <div>
                  <div className="mb-3 text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">
                    会话记忆
                  </div>
                  <div className="flex flex-col gap-4">
                    {activeConversation.map((memory) => (
                      <MemoryCard
                        key={memory.id}
                        memory={memory}
                        onDelete={memories.onDeleteMemory}
                        onEdit={memories.onEditMemory}
                      />
                    ))}
                    {activeConversation.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-app-border bg-app-panel-strong px-4 py-8 text-[14px] text-app-muted">
                        {activeConversationId == null ? "先打开一个会话。" : "当前会话还没有持久记忆。"}
                      </div>
                    ) : null}
                  </div>
                </div>

                <div>
                  <div className="mb-3 text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">
                    工作记忆
                  </div>
                  <div className="flex flex-col gap-4">
                    {activeWorking.map((memory) => (
                      <MemoryCard key={memory.id} memory={memory} onDelete={memories.onDeleteMemory} />
                    ))}
                    {activeWorking.length === 0 ? (
                      <div className="rounded-xl border border-dashed border-app-border bg-app-panel-strong px-4 py-8 text-[14px] text-app-muted">
                        暂时没有短期工作记忆。
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
