import { Check, ChevronDown, DatabaseZap, Pencil, Pin, PinOff, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import type { MemoryItem, RagReindexResult } from "../types";

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
      global_items: MemoryItem[];
      conversation_items: MemoryItem[];
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
    onEditMemory: (memory: MemoryItem) => void;
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
          className={[
            "flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left transition",
            open
              ? "border-app-accent-strong bg-[linear-gradient(180deg,#fffefb_0%,#f5ede2_100%)] shadow-[0_12px_32px_rgba(95,84,72,0.12)]"
              : "border-app-border bg-app-panel hover:border-app-border-strong hover:bg-[#fffaf2]",
          ].join(" ")}
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
            className="absolute left-0 right-0 top-[calc(100%+10px)] z-50 overflow-hidden rounded-2xl border border-app-border bg-[linear-gradient(180deg,#fffefc_0%,#f8f0e4_100%)] p-2 shadow-[0_22px_60px_rgba(34,24,16,0.16)] backdrop-blur-sm"
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
                      "flex items-center justify-between rounded-xl px-3 py-2.5 text-left text-[15px] transition",
                      option.disabled
                        ? "cursor-not-allowed opacity-45"
                        : selectedOption
                        ? "bg-app-accent text-white shadow-[0_10px_24px_rgba(95,84,72,0.2)]"
                        : "text-app-text hover:bg-white/75",
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
    return "未使用";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "未使用";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function MemoryCard({
  memory,
  onDelete,
  onEdit,
}: {
  memory: MemoryItem;
  onDelete: (memoryId: number) => void;
  onEdit: (memory: MemoryItem) => void;
}) {
  return (
    <div className="rounded-2xl border border-app-border bg-app-panel-strong p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-app-accent-soft px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-app-accent-strong">
              {MEMORY_SCOPE_LABELS[memory.scope]}
            </span>
            <span className="rounded-full border border-app-border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-app-muted">
              {MEMORY_KIND_LABELS[memory.kind]}
            </span>
            {!memory.active ? (
              <span className="rounded-full bg-[#f3e3df] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#9d3d32]">
                已停用
              </span>
            ) : null}
          </div>
          <div className="mt-3 text-[16px] font-semibold tracking-[-0.02em] text-app-text">{memory.title}</div>
          {memory.detail ? (
            <div className="mt-2 text-[14px] leading-6 text-app-muted">{memory.detail}</div>
          ) : null}
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

        <div className="flex shrink-0 items-center gap-2">
          <button
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-app-border bg-app-panel text-app-muted transition hover:text-app-text"
            onClick={() => onEdit(memory)}
            type="button"
          >
            <Pencil className="size-4" />
          </button>
          <button
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-app-border bg-app-panel text-app-muted transition hover:text-app-text"
            onClick={() => onDelete(memory.id)}
            type="button"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 text-[12px] text-app-muted">
        <span>置信度 {Math.round(memory.confidence * 100)}%</span>
        <span>{memory.pinned ? <Pin className="inline size-3.5" /> : <PinOff className="inline size-3.5" />} </span>
        <span>最近使用 {formatTimestamp(memory.last_used_at)}</span>
      </div>
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

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(22,19,16,0.24)] px-4 py-4"
      onClick={onClose}
    >
      <div
        className="flex h-full max-h-[92vh] w-full max-w-[1180px] flex-col overflow-hidden rounded-[30px] border border-app-border bg-app-panel shadow-[0_28px_120px_rgba(34,24,16,0.22)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-app-border px-7 py-6">
          <div>
            <div className="text-[30px] font-semibold tracking-[-0.04em] text-app-text">工作区设置</div>
            <div className="mt-2 text-[14px] text-app-muted">
              管理检索数据与独立记忆层，让推理时注入的信息保持紧凑、干净。
            </div>
          </div>

          <button
            className="rounded-xl px-4 py-2.5 text-[15px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
            onClick={onClose}
            type="button"
          >
            关闭
          </button>
        </div>

        <div className="grid min-h-0 flex-1 gap-0 overflow-hidden lg:grid-cols-[420px_minmax(0,1fr)]">
          <section className="app-scrollbar overflow-y-auto border-b border-app-border px-7 py-6 lg:border-r lg:border-b-0">
            <div className="flex items-center gap-3 text-app-text">
              <DatabaseZap className="size-5 text-app-accent-strong" />
              <div className="text-[18px] font-semibold tracking-[-0.02em]">RAG 数据库</div>
            </div>
            <div className="mt-4 text-[14px] leading-7 text-app-muted">
              重建 Obsidian 索引、重新生成 embedding，并刷新笔记检索元数据。
            </div>

            <div className="mt-6">
              <button
                className="rounded-xl bg-app-accent-soft px-4 py-2.5 text-[15px] font-medium text-app-accent-strong transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-60"
                disabled={isUpdating}
                onClick={onUpdateDatabase}
                type="button"
              >
                {isUpdating ? "更新中..." : "更新数据库"}
              </button>
            </div>

            {updateResult ? (
              <div className="mt-4 rounded-2xl border border-app-border bg-app-panel-strong px-4 py-3 text-[13px] leading-6 text-app-muted">
                文件数: {updateResult.indexed_files}
                <br />
                分块数: {updateResult.indexed_chunks}
                <br />
                失败数: {updateResult.failed_chunks}
              </div>
            ) : null}

            {updateError ? <div className="mt-3 text-[13px] leading-6 text-[#9d3d32]">{updateError}</div> : null}

            <div className="mt-6 rounded-2xl border border-app-border bg-app-panel-strong px-4 py-4 text-[13px] leading-6 text-app-muted">
              RAG 过滤语法:
              <br />
              <span className="text-app-text">folder:daily tag:project path:notes/roadmap</span>
              <br />
              示例:
              <br />
              <span className="text-app-text">folder:ai tag:agent 这个方案怎么拆</span>
            </div>

            <div className="mt-8 border-t border-app-border pt-6">
              <div className="text-[16px] font-semibold tracking-[-0.02em] text-app-text">记忆机制</div>
              <div className="mt-3 text-[14px] leading-7 text-app-muted">
                每轮对话完成后会在后台抽取记忆，单独存储，不和聊天历史混在一起；调用时只注入一份紧凑摘要，而不是把长上下文整段重放。被 Pin 的记忆会作为固定上下文常驻注入。
              </div>
            </div>
          </section>

          <section className="app-scrollbar overflow-y-auto px-7 py-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-[18px] font-semibold tracking-[-0.02em] text-app-text">记忆管理</div>
                <div className="mt-2 text-[14px] text-app-muted">
                  全局记忆会跨会话保留；会话记忆只跟随当前线程。
                </div>
                <div className="mt-2 text-[13px] text-app-muted">
                  当前会话:
                  {" "}
                  <span className="text-app-text">
                    {activeConversationId != null ? activeConversationTitle || `会话 #${activeConversationId}` : "未选择"}
                  </span>
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  className="inline-flex items-center gap-2 rounded-xl border border-app-border bg-app-panel-strong px-4 py-2.5 text-[14px] font-medium text-app-text transition hover:bg-app-panel-soft"
                  onClick={memories.onCreateGlobalMemory}
                  type="button"
                >
                  <Plus className="size-4" />
                  新建全局记忆
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-xl border border-app-border bg-app-panel-strong px-4 py-2.5 text-[14px] font-medium text-app-text transition hover:bg-app-panel-soft disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={!memories.canCreateConversationMemory}
                  onClick={memories.onCreateConversationMemory}
                  type="button"
                >
                  <Plus className="size-4" />
                  新建会话记忆
                </button>
                <button
                  className="inline-flex items-center gap-2 rounded-xl border border-app-border bg-app-panel px-4 py-2.5 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
                  onClick={memories.onRefresh}
                  type="button"
                >
                  <RefreshCw className={`size-4 ${memories.isLoading ? "animate-spin" : ""}`} />
                  刷新
                </button>
              </div>
            </div>

            {memories.error ? <div className="mt-4 text-[13px] leading-6 text-[#9d3d32]">{memories.error}</div> : null}

            {memories.editor ? (
              <div className="mt-6 rounded-[26px] border border-app-border bg-app-panel-strong p-5">
                <div className="flex items-center justify-between gap-4">
                  <div className="text-[16px] font-semibold tracking-[-0.02em] text-app-text">
                    {memories.editor.id == null ? "新建记忆" : "编辑记忆"}
                  </div>
                  <div className="flex gap-2">
                    <button
                      className="rounded-xl px-4 py-2.5 text-[14px] font-medium text-app-muted transition hover:bg-app-panel hover:text-app-text"
                      onClick={memories.onCancelEditing}
                      type="button"
                    >
                      取消
                    </button>
                    <button
                      className="rounded-xl bg-app-accent-soft px-4 py-2.5 text-[14px] font-medium text-app-accent-strong transition hover:bg-app-panel disabled:cursor-not-allowed disabled:opacity-60"
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
                      className="rounded-2xl border border-app-border bg-app-panel px-4 py-3 text-[14px] text-app-text"
                      onChange={(event) => memories.onChangeEditor({ title: event.target.value })}
                      placeholder="一条卡片只写一个稳定记忆"
                      value={memories.editor.title}
                    />
                  </label>

                  <label className="md:col-span-2 flex flex-col gap-2">
                    <FormLabel>详情</FormLabel>
                    <textarea
                      className="min-h-[120px] rounded-2xl border border-app-border bg-app-panel px-4 py-3 text-[14px] leading-6 text-app-text"
                      onChange={(event) => memories.onChangeEditor({ detail: event.target.value })}
                      placeholder="可选，补充细节、例外情况或额外上下文"
                      value={memories.editor.detail}
                    />
                  </label>

                  <label className="flex flex-col gap-2">
                    <FormLabel>标签</FormLabel>
                    <input
                      className="rounded-2xl border border-app-border bg-app-panel px-4 py-3 text-[14px] text-app-text"
                      onChange={(event) => memories.onChangeEditor({ tagsText: event.target.value })}
                      placeholder="写作, 编程, 产品"
                      value={memories.editor.tagsText}
                    />
                  </label>

                  <label className="flex flex-col gap-2">
                    <FormLabel>置信度</FormLabel>
                    <input
                      className="rounded-2xl border border-app-border bg-app-panel px-4 py-3 text-[14px] text-app-text"
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

            <div className="mt-6 grid gap-6 xl:grid-cols-2">
              <div>
                <div className="mb-3 text-[14px] font-semibold uppercase tracking-[0.14em] text-app-muted">
                  全局记忆
                </div>
                <div className="flex flex-col gap-4">
                  {memories.collection.global_items.map((memory) => (
                    <MemoryCard
                      key={memory.id}
                      memory={memory}
                      onDelete={memories.onDeleteMemory}
                      onEdit={memories.onEditMemory}
                    />
                  ))}
                  {memories.collection.global_items.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-app-border bg-app-panel-strong px-4 py-8 text-[14px] text-app-muted">
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
                  {memories.collection.conversation_items.map((memory) => (
                    <MemoryCard
                      key={memory.id}
                      memory={memory}
                      onDelete={memories.onDeleteMemory}
                      onEdit={memories.onEditMemory}
                    />
                  ))}
                  {memories.collection.conversation_items.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-app-border bg-app-panel-strong px-4 py-8 text-[14px] text-app-muted">
                      {activeConversationId == null
                        ? "先打开一个会话，才能管理会话级记忆。"
                        : "当前会话还没有记忆。"}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>

            {!memories.hasMemories && !memories.editor ? (
              <div className="mt-6 rounded-2xl border border-app-border bg-app-panel-strong px-4 py-4 text-[14px] leading-7 text-app-muted">
                对话完成后会自动开始抽取记忆。你也可以在这里手动补充稳定偏好、项目约束和长期目标。
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}
