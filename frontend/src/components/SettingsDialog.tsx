import {
  Check,
  ChevronDown,
  Database,
  FileText,
  FileUp,
  Pencil,
  Pin,
  PinOff,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import type { KnowledgeDocument, KnowledgeStatus, MemoryDocument, MemoryItem } from "../types";

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

type SettingsTab = "memory" | "knowledge";

interface SettingsDialogProps {
  open: boolean;
  activeConversationId: number | null;
  activeConversationTitle: string;
  knowledge: {
    documents: KnowledgeDocument[];
    status: KnowledgeStatus;
    error: string | null;
    isLoading: boolean;
    isSaving: boolean;
    isUpdating: boolean;
    isAllSelected: boolean;
    onDelete: (documentId: number) => void;
    onDeleteSelected: () => void;
    onRefresh: () => void;
    onReindex: (documentId: number) => void;
    onSelectAll: () => void;
    onSelectOne: (documentId: number) => void;
    onUpdate: () => void;
    onUploadMany: (files: File[]) => void;
    selectedDocumentIds: number[];
    updateResult: {
      started: boolean;
      scheduled_documents: number;
      indexing_documents: number;
      ready_documents: number;
      failed_documents: number;
      chunk_count: number;
    } | null;
  };
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

function StatChip({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full border border-app-border bg-app-panel-strong px-3 py-1.5 text-[13px] text-app-muted">
      {children}
    </span>
  );
}

function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-app-border bg-app-panel-strong px-4 py-8 text-[14px] text-app-muted">
      {children}
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

function formatBytes(value: number): string {
  if (value >= 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (value >= 1024) {
    return `${Math.round(value / 1024)} KB`;
  }
  return `${value} B`;
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

function TabButton({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      className={[
        "inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-[14px] font-medium transition",
        active ? "bg-app-accent text-white shadow-sm" : "text-app-muted hover:bg-app-panel hover:text-app-text",
      ].join(" ")}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
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

function KnowledgeCard({
  document,
  onDelete,
  onReindex,
  onSelect,
  selected,
}: {
  document: KnowledgeDocument;
  onDelete: (documentId: number) => void;
  onReindex: (documentId: number) => void;
  onSelect: (documentId: number) => void;
  selected: boolean;
}) {
  const statusLabel =
    document.status === "ready"
      ? "可用"
      : document.status === "indexing"
        ? "索引中"
        : document.status === "failed"
          ? "失败"
          : "待处理";

  return (
    <div className="rounded-xl border border-app-border bg-app-panel-strong p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <label className="mt-0.5 flex shrink-0 items-center">
            <input
              checked={selected}
              className="h-4 w-4 rounded border-app-border text-app-accent-strong focus:ring-app-accent-strong"
              onChange={() => onSelect(document.id)}
              type="checkbox"
            />
          </label>

          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-app-accent-soft px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-accent-strong">
                Markdown
              </span>
              <span className="rounded-full border border-app-border px-2.5 py-1 text-[11px] font-semibold tracking-[0.12em] text-app-muted">
                {statusLabel}
              </span>
            </div>
            <div className="mt-3 truncate text-[16px] font-semibold tracking-[-0.02em] text-app-text">
              {document.title}
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-[12px] text-app-muted">
              <span>{formatBytes(document.size_bytes)}</span>
              <span>{document.chunk_count} 分块</span>
              <span>{formatTimestamp(document.updated_at)}</span>
            </div>
            {document.error_message ? (
              <div className="mt-3 text-[13px] leading-6 text-[#9d3d32]">{document.error_message}</div>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-app-border bg-app-panel text-app-muted transition hover:text-app-text"
            onClick={() => onReindex(document.id)}
            type="button"
          >
            <RefreshCw className="size-4" />
          </button>
          <button
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-app-border bg-app-panel text-app-muted transition hover:text-app-text"
            onClick={() => onDelete(document.id)}
            type="button"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export function SettingsDialog({
  open,
  activeConversationId,
  activeConversationTitle,
  knowledge,
  memories,
  onClose,
}: SettingsDialogProps) {
  const uploadInputRef = useRef<HTMLInputElement | null>(null);
  const [activeTab, setActiveTab] = useState<SettingsTab>("memory");

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
    if (open) {
      setActiveTab("memory");
    }
  }, [open]);

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
  const currentConversationLabel =
    activeConversationId != null ? activeConversationTitle || `会话 #${activeConversationId}` : "未选择";

  const activeTabTitle = activeTab === "memory" ? "记忆管理" : "知识库管理";
  const activeTabDescription =
    activeTab === "memory"
      ? "管理会话记忆、会话记忆和记忆空间"
      : "上传 md 文档并统一更新知识库";

  const handlePickMarkdown = () => uploadInputRef.current?.click();
  const knowledgeProgress =
    knowledge.updateResult && knowledge.updateResult.scheduled_documents > 0
      ? Math.max(
          0,
          Math.min(
            100,
            Math.round(
              ((knowledge.updateResult.scheduled_documents - knowledge.status.indexing_document_count) /
                knowledge.updateResult.scheduled_documents) *
                100,
            ),
          ),
        )
      : null;

  const memoryView = (
    <div className="space-y-8">
      <div className="space-y-3">
        <SectionTitle
          icon={<FileText className="size-5 text-app-accent-strong" />}
          subtitle=""
          title="记忆空间"
        />
        <div className="flex flex-wrap gap-2">
          <StatChip>当前会话: {currentConversationLabel}</StatChip>
          <StatChip>全局记忆: {activeGlobal.length}</StatChip>
          <StatChip>会话记忆: {activeConversation.length}</StatChip>
          <StatChip>记忆文档: {memories.collection.documents.length}</StatChip>
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
          刷新记忆
        </button>
      </div>

      {memories.error ? <div className="text-[13px] leading-6 text-[#9d3d32]">{memories.error}</div> : null}

      {memories.editor ? (
        <div className="rounded-[20px] border border-app-border bg-app-panel-strong p-5">
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

      <div>
        <div className="mb-3 text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">记忆文档</div>
        <div className="grid gap-4 xl:grid-cols-3">
          {memories.collection.documents.map((document) => (
            <DocumentCard document={document} key={document.id} />
          ))}
          {memories.collection.documents.length === 0 ? <EmptyState>还没有文档，系统会在记忆稳定后自动生成。</EmptyState> : null}
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <div>
          <div className="mb-3 text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">全局记忆</div>
          <div className="flex flex-col gap-4">
            {activeGlobal.map((memory) => (
              <MemoryCard
                key={memory.id}
                memory={memory}
                onDelete={memories.onDeleteMemory}
                onEdit={memories.onEditMemory}
              />
            ))}
            {activeGlobal.length === 0 ? <EmptyState>还没有全局记忆。</EmptyState> : null}
          </div>
        </div>

        <div>
          <div className="mb-3 text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">会话记忆</div>
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
              <EmptyState>{activeConversationId == null ? "先打开一个会话。" : "当前会话还没有持久记忆。"}</EmptyState>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );

  const knowledgeView = (
    <div className="space-y-8">
      <div className="space-y-3">
        <SectionTitle
          icon={<Database className="size-5 text-app-accent-strong" />}
          subtitle=""
          title="知识库空间"
        />
        <div className="flex flex-wrap gap-2">
          <StatChip>
            知识文档: {knowledge.status.document_count}/{knowledge.status.max_documents_per_user || 0}
          </StatChip>
          <StatChip>待更新: {knowledge.status.pending_document_count}</StatChip>
          <StatChip>索引中: {knowledge.status.indexing_document_count}</StatChip>
          <StatChip>可用文档: {knowledge.status.ready_document_count}</StatChip>
          <StatChip>分块: {knowledge.status.chunk_count}</StatChip>
          <StatChip>已用空间: {formatBytes(knowledge.status.total_size_bytes)}</StatChip>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel-strong px-4 py-2.5 text-[14px] font-medium text-app-text transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-50"
          disabled={knowledge.isSaving}
          onClick={handlePickMarkdown}
          type="button"
        >
          <FileUp className="size-4" />
          上传 Markdown
        </button>
        <button
          className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel px-4 py-2.5 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text disabled:cursor-not-allowed disabled:opacity-50"
          disabled={knowledge.selectedDocumentIds.length === 0 || knowledge.isSaving}
          onClick={knowledge.onDeleteSelected}
          type="button"
        >
          <Trash2 className="size-4" />
          删除 {knowledge.selectedDocumentIds.length > 0 ? `(${knowledge.selectedDocumentIds.length})` : ""}
        </button>
        <button
          className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel px-4 py-2.5 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
          onClick={knowledge.onRefresh}
          type="button"
        >
          <RefreshCw className={`size-4 ${knowledge.isLoading ? "animate-spin" : ""}`} />
          刷新
        </button>
        <button
          className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel px-4 py-2.5 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text disabled:cursor-not-allowed disabled:opacity-50"
          disabled={knowledge.isUpdating}
          onClick={knowledge.onUpdate}
          type="button"
        >
          <RefreshCw className={`size-4 ${knowledge.isUpdating ? "animate-spin" : ""}`} />
          {knowledge.isUpdating ? "更新中..." : "更新知识库"}
        </button>
        {knowledgeProgress != null ? (
          <div className="flex min-w-[180px] items-center gap-3">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-app-panel-strong">
              <div
                className="h-full rounded-full bg-app-accent transition-[width] duration-300"
                style={{ width: `${knowledgeProgress}%` }}
              />
            </div>
            <div className="w-10 text-right text-[12px] font-medium text-app-muted">{knowledgeProgress}%</div>
          </div>
        ) : null}
      </div>

      {knowledge.error ? <div className="text-[13px] leading-6 text-[#9d3d32]">{knowledge.error}</div> : null}

      {knowledge.updateResult ? (
        <button
          className="w-full rounded-xl border border-app-border bg-app-panel-strong px-4 py-3 text-left text-[13px] text-app-muted transition hover:bg-app-panel disabled:cursor-not-allowed disabled:opacity-60"
          disabled={knowledge.isUpdating}
          onClick={knowledge.onUpdate}
          type="button"
        >
          {knowledge.updateResult.started ? "已提交知识库更新" : "知识库状态"}: 排队{" "}
          {knowledge.updateResult.scheduled_documents} / 索引中 {knowledge.updateResult.indexing_documents} / 可用{" "}
          {knowledge.updateResult.ready_documents} / 失败 {knowledge.updateResult.failed_documents} / 分块{" "}
          {knowledge.updateResult.chunk_count}
        </button>
      ) : null}

      <div>
        <div className="mb-3 flex items-center gap-3">
          <div className="text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">知识库文档</div>
          {knowledge.documents.length > 0 ? (
            <label className="inline-flex items-center">
              <input
                aria-label="全选知识库文档"
                checked={knowledge.isAllSelected}
                className="h-4 w-4 rounded border-app-border text-app-accent-strong focus:ring-app-accent-strong"
                onChange={knowledge.onSelectAll}
                type="checkbox"
              />
            </label>
          ) : null}
        </div>

        <div className="grid gap-4 xl:grid-cols-3">
          {knowledge.documents.map((document) => (
            <KnowledgeCard
              document={document}
              key={document.id}
              onDelete={knowledge.onDelete}
              onReindex={knowledge.onReindex}
              onSelect={knowledge.onSelectOne}
              selected={knowledge.selectedDocumentIds.includes(document.id)}
            />
          ))}
          {knowledge.documents.length === 0 ? (
            <EmptyState>先上传 `.md` 文档，再点“更新知识库”完成切分和索引。</EmptyState>
          ) : null}
        </div>
      </div>
    </div>
  );

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(22,19,16,0.24)] px-4 py-4"
      onClick={onClose}
    >
      <div
        className="flex h-full max-h-[92vh] w-full max-w-[1160px] flex-col overflow-hidden rounded-[24px] border border-app-border bg-app-panel shadow-[0_28px_120px_rgba(34,24,16,0.22)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b border-app-border px-7 py-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-4">
                <div className="text-[30px] font-semibold tracking-[-0.04em] text-app-text">{activeTabTitle}</div>
                <div className="inline-flex rounded-2xl border border-app-border bg-app-panel-strong p-1.5">
                  <TabButton active={activeTab === "memory"} onClick={() => setActiveTab("memory")}>
                    记忆
                  </TabButton>
                  <TabButton active={activeTab === "knowledge"} onClick={() => setActiveTab("knowledge")}>
                    知识库
                  </TabButton>
                </div>
              </div>
              <div className="mt-2 text-[14px] leading-7 text-app-muted">{activeTabDescription}</div>
            </div>

            <button
              className="rounded-lg px-4 py-2.5 text-[15px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
              onClick={onClose}
              type="button"
            >
              关闭
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-hidden">
          <section className="app-scrollbar h-full overflow-y-auto px-7 py-6">
            <input
              accept=".md,text/markdown"
              className="hidden"
              multiple
              onChange={(event) => {
                const files = Array.from(event.target.files ?? []);
                if (files.length > 0) {
                  knowledge.onUploadMany(files);
                }
                event.currentTarget.value = "";
              }}
              ref={uploadInputRef}
              type="file"
            />

            {activeTab === "memory" ? memoryView : knowledgeView}
          </section>
        </div>
      </div>
    </div>
  );
}
