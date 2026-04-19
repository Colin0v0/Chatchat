import { MessageSquare, Scale, Search } from "lucide-react";
import { useEffect, useRef } from "react";

import type { ConversationSummary, DebateSessionSummary } from "../../../../types";
import { cn } from "./styles";

interface SidebarSearchDialogProps {
  activity?: Record<number, { running: boolean; unread: boolean }>;
  debateActivity?: Record<number, { running: boolean; unread: boolean }>;
  items: ConversationSummary[];
  debateItems: DebateSessionSummary[];
  open: boolean;
  query: string;
  onClose: () => void;
  onQueryChange: (value: string) => void;
  onSelect: (conversationId: number) => void;
  onSelectDebate: (sessionId: number) => void;
}

export function SidebarSearchDialog({
  activity = {},
  debateActivity = {},
  items,
  debateItems,
  open,
  query,
  onClose,
  onQueryChange,
  onSelect,
  onSelectDebate,
}: SidebarSearchDialogProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    const timeoutId = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(timeoutId);
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
  }, [onClose, open]);

  if (!open) {
    return null;
  }

  const hasQuery = query.trim().length > 0;
  const emptyMessage = hasQuery ? "No sessions matched your search." : "Start typing to search sessions.";
  const combinedItems = [
    ...items.map((item) => ({
      id: item.id,
      kind: "chat" as const,
      title: item.title,
      updatedAt: item.updated_at,
    })),
    ...debateItems.map((item) => ({
      id: item.id,
      kind: "debate" as const,
      title: item.topic,
      updatedAt: item.updated_at,
    })),
  ].sort((left, right) => {
    const leftTime = left.updatedAt ? Date.parse(left.updatedAt) : 0;
    const rightTime = right.updatedAt ? Date.parse(right.updatedAt) : 0;
    return rightTime - leftTime;
  });

  return (
    <div
      className="fixed inset-0 z-40 flex items-start justify-center bg-[rgba(22,19,16,0.10)] px-4 pt-20 backdrop-blur-[6px]"
      onClick={onClose}
    >
      <div className="w-full max-w-[800px]" onClick={(event) => event.stopPropagation()}>
        <div className="rounded-[16px] border border-app-border bg-app-panel shadow-[0_24px_64px_rgba(34,24,16,0.16)]">
          <div className="flex items-center gap-3 px-4 py-4">
            <Search className="size-5 shrink-0 text-app-muted" />
            <input
              className="min-w-0 flex-1 bg-transparent text-[18px] tracking-[-0.03em] text-app-text outline-none placeholder:text-app-muted"
              onChange={(event) => onQueryChange(event.target.value)}
              placeholder="Search"
              ref={inputRef}
              value={query}
            />
            <button
              className="rounded-[10px] border border-app-border bg-app-panel-strong px-3 py-1.75 text-[13px] text-app-muted transition hover:text-app-text"
              onClick={onClose}
              type="button"
            >
              退出
            </button>
          </div>

          <div className="max-h-[420px] overflow-y-auto border-t border-app-border/80 px-3 py-3">
            {combinedItems.length === 0 ? (
              <div className="px-3 py-5 text-[14px] text-app-muted">{emptyMessage}</div>
            ) : (
              <div className="flex flex-col gap-1">
                {combinedItems.map((item) => {
                  const itemActivity = item.kind === "chat" ? activity[item.id] : debateActivity[item.id];

                  return (
                    <button
                      className={cn(
                        "flex min-w-0 items-center justify-between rounded-[10px] px-3 py-3 text-left transition-colors",
                        "hover:bg-app-panel-soft focus:outline-none focus-visible:outline-none",
                      )}
                      key={`${item.kind}:${item.id}`}
                      onClick={() => {
                        if (item.kind === "chat") {
                          onSelect(item.id);
                        } else {
                          onSelectDebate(item.id);
                        }
                        onClose();
                      }}
                      type="button"
                    >
                      <span className="flex min-w-0 items-center gap-2.5">
                        {item.kind === "chat" ? (
                          <MessageSquare className="size-4 shrink-0 text-app-muted" />
                        ) : (
                          <Scale className="size-4 shrink-0 text-app-muted" />
                        )}
                        <span className="truncate text-[15px] font-medium tracking-[-0.02em] text-app-text">
                          {item.title}
                        </span>
                      </span>
                      {itemActivity?.running ? (
                        <span className="ml-3 flex h-5 w-5 shrink-0 items-center justify-center text-app-muted">
                          <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-app-muted/35 border-t-app-muted" />
                        </span>
                      ) : itemActivity?.unread ? (
                        <span className="ml-3 inline-flex h-2.5 w-2.5 shrink-0 rounded-full bg-app-accent-strong" />
                      ) : null}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
