import { Plus, Scale } from "lucide-react";

import { WorkspacePage } from "../../../shared/ui/WorkspacePage";

export function DebatesHomeView({ onNewDebate }: { onNewDebate: () => void }) {
  return (
    <WorkspacePage
      actions={
        <button
          className="inline-flex items-center gap-2 rounded-lg border border-app-border bg-app-panel-strong px-4 py-2.5 text-[14px] font-medium text-app-text transition hover:bg-app-panel-soft"
          onClick={onNewDebate}
          type="button"
        >
          <Plus className="size-4" />
          New debate
        </button>
      }
      subtitle="从左侧历史进入已有辩论，或者新建一场新的辩论。"
      title="Debates"
    >
      <div className="flex min-h-[320px] items-center justify-center rounded-[24px] border border-dashed border-app-border bg-app-panel-strong px-8 py-12">
        <div className="max-w-[520px] text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-app-accent-soft text-app-accent-strong">
            <Scale className="size-6" />
          </div>
          <div className="mt-5 text-[26px] font-semibold tracking-[-0.04em] text-app-text">Open a debate workspace</div>
          <div className="mt-3 text-[15px] leading-7 text-app-muted">
            这里展示辩论创建页和辩论房间。左侧 `Recents` 会统一列出聊天与辩论，进入时会通过图标区分模式。
          </div>
          <button
            className="mt-6 inline-flex items-center gap-2 rounded-lg bg-app-accent-soft px-4 py-2.5 text-[14px] font-medium text-app-accent-strong transition hover:bg-app-panel-soft"
            onClick={onNewDebate}
            type="button"
          >
            <Plus className="size-4" />
            New debate
          </button>
        </div>
      </div>
    </WorkspacePage>
  );
}
