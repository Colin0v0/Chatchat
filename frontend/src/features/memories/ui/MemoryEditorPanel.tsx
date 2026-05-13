import { Check, X } from "lucide-react";

import type { MemoryKind } from "../../../types";
import type { MemoryEditorState } from "../model/useMemoryManager";
import { MEMORY_KIND_LABELS } from "./memoryPresentation";

const EDITOR_INPUT_CLASS =
  "w-full rounded-[8px] border border-app-border bg-app-panel px-3 py-2.5 text-[14px] text-app-text outline-none transition placeholder:text-app-muted/60 focus:border-app-border-strong";

const MEMORY_KIND_OPTIONS: MemoryKind[] = ["profile", "preference", "goal", "project", "fact", "constraint"];

interface MemoryEditorPanelProps {
  editor: NonNullable<MemoryEditorState>;
  isSaving: boolean;
  onCancel: () => void;
  onChange: (patch: Record<string, unknown>) => void;
  onSave: () => void;
}

function EditorLabel({ children }: { children: string }) {
  return <span className="text-[12px] font-medium text-app-muted">{children}</span>;
}

function EditorSwitch({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      aria-checked={checked}
      className={[
        "inline-flex h-9 items-center gap-2 rounded-[8px] border px-3 text-[13px] font-medium transition",
        checked
          ? "border-app-border bg-app-accent-soft text-app-accent-strong"
          : "border-app-border bg-app-panel text-app-muted hover:bg-app-panel-soft hover:text-app-text",
      ].join(" ")}
      onClick={() => onChange(!checked)}
      role="switch"
      type="button"
    >
      <span className={["h-2 w-2 rounded-full", checked ? "bg-app-accent-strong" : "bg-app-muted/40"].join(" ")} />
      {label}
    </button>
  );
}

export function MemoryEditorPanel({ editor, isSaving, onCancel, onChange, onSave }: MemoryEditorPanelProps) {
  return (
    <section className="rounded-[8px] border border-app-border bg-app-panel-strong p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[17px] font-semibold text-app-text">{editor.id == null ? "新建记忆" : "编辑记忆"}</div>
          <div className="mt-1 text-[13px] leading-5 text-app-muted">
            {editor.scope === "global" ? "长期记忆" : "当前会话记忆"}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            className="inline-flex h-9 items-center gap-1.5 rounded-[8px] px-3 text-[13px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
            onClick={onCancel}
            type="button"
          >
            <X className="size-4" />
            取消
          </button>
          <button
            className="inline-flex h-9 items-center gap-1.5 rounded-[8px] bg-app-accent-soft px-3 text-[13px] font-medium text-app-accent-strong transition hover:bg-[#e7ddcf] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isSaving}
            onClick={onSave}
            type="button"
          >
            <Check className="size-4" />
            {isSaving ? "保存中" : "保存"}
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-[220px_minmax(0,1fr)]">
        <label className="flex min-w-0 flex-col gap-2">
          <EditorLabel>类型</EditorLabel>
          <select
            className={EDITOR_INPUT_CLASS}
            onChange={(event) => onChange({ kind: event.target.value as MemoryKind })}
            value={editor.kind}
          >
            {MEMORY_KIND_OPTIONS.map((kind) => (
              <option key={kind} value={kind}>
                {MEMORY_KIND_LABELS[kind]}
              </option>
            ))}
          </select>
        </label>

        <label className="flex min-w-0 flex-col gap-2">
          <EditorLabel>标题</EditorLabel>
          <input
            className={EDITOR_INPUT_CLASS}
            onChange={(event) => onChange({ title: event.target.value })}
            placeholder="一条稳定事实"
            value={editor.title}
          />
        </label>

        <label className="flex min-w-0 flex-col gap-2 md:col-span-2">
          <EditorLabel>详情</EditorLabel>
          <textarea
            className={`${EDITOR_INPUT_CLASS} min-h-[112px] resize-y leading-6`}
            onChange={(event) => onChange({ detail: event.target.value })}
            placeholder="适用范围、边界条件、相关背景"
            value={editor.detail}
          />
        </label>

        <label className="flex min-w-0 flex-col gap-2">
          <EditorLabel>标签</EditorLabel>
          <input
            className={EDITOR_INPUT_CLASS}
            onChange={(event) => onChange({ tagsText: event.target.value })}
            placeholder="写作, 编程, 产品"
            value={editor.tagsText}
          />
        </label>

        <label className="flex min-w-0 flex-col gap-2">
          <EditorLabel>置信度</EditorLabel>
          <input
            className={EDITOR_INPUT_CLASS}
            max="1"
            min="0"
            onChange={(event) => onChange({ confidenceText: event.target.value })}
            step="0.05"
            type="number"
            value={editor.confidenceText}
          />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <EditorSwitch checked={editor.pinned} label="固定注入" onChange={(checked) => onChange({ pinned: checked })} />
        <EditorSwitch checked={editor.active} label="启用" onChange={(checked) => onChange({ active: checked })} />
      </div>
    </section>
  );
}
