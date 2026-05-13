import type { MemoryItem } from "../../../types";
import { MemoryCard, MemoryEmptyState } from "./MemoryCard";

export type MemoryInventoryTab = "global" | "conversation" | "working";

interface MemoryInventoryPanelProps {
  activeTab: MemoryInventoryTab;
  conversationItems: MemoryItem[];
  globalItems: MemoryItem[];
  onDeleteMemory: (memoryId: number) => void;
  onEditMemory: (memory: MemoryItem) => void;
  onTabChange: (tab: MemoryInventoryTab) => void;
  workingItems: MemoryItem[];
}

const TAB_LABELS: Record<MemoryInventoryTab, string> = {
  global: "长期",
  conversation: "当前会话",
  working: "工作中",
};

function tabItems(
  tab: MemoryInventoryTab,
  globalItems: MemoryItem[],
  conversationItems: MemoryItem[],
  workingItems: MemoryItem[],
) {
  if (tab === "global") {
    return globalItems;
  }
  if (tab === "conversation") {
    return conversationItems;
  }
  return workingItems;
}

function emptyCopy(tab: MemoryInventoryTab) {
  if (tab === "global") {
    return "还没有长期记忆。";
  }
  if (tab === "conversation") {
    return "当前会话还没有专属记忆。";
  }
  return "现在没有工作记忆。";
}

export function MemoryInventoryPanel({
  activeTab,
  conversationItems,
  globalItems,
  onDeleteMemory,
  onEditMemory,
  onTabChange,
  workingItems,
}: MemoryInventoryPanelProps) {
  const counts: Record<MemoryInventoryTab, number> = {
    global: globalItems.length,
    conversation: conversationItems.length,
    working: workingItems.length,
  };
  const visibleItems = tabItems(activeTab, globalItems, conversationItems, workingItems);

  return (
    <section className="min-w-0">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[17px] font-semibold text-app-text">记忆库</div>
        </div>
        <div className="flex min-w-0 overflow-x-auto rounded-[8px] border border-app-border bg-app-panel-strong p-1">
          {(["global", "conversation", "working"] as MemoryInventoryTab[]).map((tab) => {
            const active = activeTab === tab;
            return (
              <button
                className={[
                  "inline-flex h-9 shrink-0 items-center gap-2 rounded-[8px] px-3 text-[13px] font-medium transition",
                  active ? "bg-app-panel-soft text-app-text" : "text-app-muted hover:bg-app-panel hover:text-app-text",
                ].join(" ")}
                key={tab}
                onClick={() => onTabChange(tab)}
                type="button"
              >
                {TAB_LABELS[tab]}
                <span className="rounded-[8px] bg-app-panel px-1.5 py-0.5 text-[11px] text-app-muted">{counts[tab]}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid gap-3">
        {visibleItems.map((memory) => (
          <MemoryCard
            key={memory.id}
            memory={memory}
            onDelete={onDeleteMemory}
            onEdit={memory.scope === "working" ? undefined : onEditMemory}
          />
        ))}
        {visibleItems.length === 0 ? <MemoryEmptyState>{emptyCopy(activeTab)}</MemoryEmptyState> : null}
      </div>
    </section>
  );
}
