import { ChevronDown, MessageSquarePlus, MoreHorizontal, PanelLeftOpen, Pencil, Scale, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface MainHeaderProps {
  title: string;
  showTitle?: boolean;
  sidebarOpen: boolean;
  isDesktop: boolean;
  activeItemId?: number | null;
  activeItemKind?: "chat" | "debate" | null;
  activeItemTitle?: string;
  onRenameItem?: (itemId: number, title: string, kind: "chat" | "debate") => void | Promise<void>;
  onDeleteItem?: (itemId: number, kind: "chat" | "debate") => void | Promise<void>;
  onToggleSidebar: () => void;
  onNewChat?: () => void;
  onNewDebate?: () => void;
}

type HeaderDialogState =
  | {
      type: "rename";
      value: string;
    }
  | {
      type: "delete";
    }
  | null;

export function MainHeader({
  title,
  showTitle = true,
  sidebarOpen,
  isDesktop,
  activeItemId = null,
  activeItemKind = null,
  activeItemTitle = "",
  onRenameItem,
  onDeleteItem,
  onToggleSidebar,
  onNewChat,
  onNewDebate,
}: MainHeaderProps) {
  const [actionMenuOpen, setActionMenuOpen] = useState(false);
  const [createMenuOpen, setCreateMenuOpen] = useState(false);
  const [dialogState, setDialogState] = useState<HeaderDialogState>(null);
  const actionMenuRef = useRef<HTMLDivElement | null>(null);
  const createMenuRef = useRef<HTMLDivElement | null>(null);
  const hasActiveItem = activeItemId !== null && activeItemKind !== null;
  const itemLabel = activeItemKind === "debate" ? "debate" : "chat";

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (dialogState) {
        return;
      }

      const target = event.target as Node;
      if (!actionMenuRef.current?.contains(target)) {
        setActionMenuOpen(false);
      }
      if (!createMenuRef.current?.contains(target)) {
        setCreateMenuOpen(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, [dialogState]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setDialogState(null);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const titleMenu = (
    <div className="relative min-w-0" ref={createMenuRef}>
      <button
        aria-label="Create session"
        className="inline-flex min-w-0 items-center gap-2 py-1 text-[20px] font-semibold leading-none tracking-[-0.04em] text-app-text focus:outline-none focus-visible:ring-2 focus-visible:ring-app-border-strong md:text-[24px]"
        onClick={() => setCreateMenuOpen((current) => !current)}
        type="button"
      >
        <span className="truncate">{title}</span>
        <ChevronDown className={`size-4 shrink-0 text-[#5f564a] transition ${createMenuOpen ? "rotate-180" : ""}`} />
      </button>

      {createMenuOpen ? (
        <div className="absolute left-0 top-[calc(100%+8px)] z-30 min-w-[220px] overflow-hidden rounded-lg border border-app-border bg-app-panel-strong shadow-[0_12px_30px_rgba(39,28,18,0.08)]">
          <button
            className="flex w-full items-center gap-3 px-4 py-3 text-left text-[15px] font-medium tracking-[-0.02em] text-[#5f564a] transition hover:bg-app-panel-soft"
            onClick={() => {
              setCreateMenuOpen(false);
              onNewChat?.();
            }}
            type="button"
          >
            <MessageSquarePlus className="size-4 shrink-0 text-[#5f564a]" />
            <span>新建聊天</span>
          </button>
          <div className="border-t border-app-border/80" role="separator" />
          <button
            className="flex w-full items-center gap-3 px-4 py-3 text-left text-[15px] font-medium tracking-[-0.02em] text-[#5f564a] transition hover:bg-app-panel-soft"
            onClick={() => {
              setCreateMenuOpen(false);
              onNewDebate?.();
            }}
            type="button"
          >
            <Scale className="size-4 shrink-0 text-[#5f564a]" />
            <span>发起辩论</span>
          </button>
        </div>
      ) : null}
    </div>
  );

  const actionMenu = hasActiveItem ? (
    <div className="relative" ref={actionMenuRef}>
      <button
        aria-label="Session actions"
        className="flex h-9 w-9 items-center justify-center rounded-lg text-app-muted transition hover:text-app-text focus:outline-none focus-visible:ring-2 focus-visible:ring-app-border-strong"
        onClick={() => setActionMenuOpen((current) => !current)}
        type="button"
      >
        <MoreHorizontal className="size-4" />
      </button>

      {actionMenuOpen ? (
        <div className="absolute right-0 top-[calc(100%+6px)] z-30 min-w-[180px] overflow-hidden rounded-lg border border-app-border bg-app-panel-strong shadow-[0_12px_30px_rgba(39,28,18,0.08)]">
          <button
            className="flex w-full items-center gap-3 px-4 py-3 text-left text-[15px] font-medium tracking-[-0.02em] text-[#5f564a] transition hover:bg-app-panel-soft"
            onClick={() => {
              setActionMenuOpen(false);
              setDialogState({
                type: "rename",
                value: activeItemTitle,
              });
            }}
            type="button"
          >
            <Pencil className="size-4 text-[#5f564a]" />
            <span>Rename</span>
          </button>
          <div className="border-t border-app-border/80" role="separator" />
          <button
            className="flex w-full items-center gap-3 px-4 py-3 text-left text-[15px] font-medium tracking-[-0.02em] text-[#9d3d32] transition hover:bg-app-panel-soft"
            onClick={() => {
              setActionMenuOpen(false);
              setDialogState({ type: "delete" });
            }}
            type="button"
          >
            <Trash2 className="size-4" />
            <span>Delete</span>
          </button>
        </div>
      ) : null}
    </div>
  ) : null;

  return (
    <>
      <header className="relative flex h-[68px] items-center justify-between px-4 md:px-6">
        {showTitle ? titleMenu : <div />}

        {isDesktop ? <div className="flex items-center gap-2">{actionMenu}</div> : null}

        {!isDesktop ? (
          <div className="fixed top-4 right-4 z-30 flex items-center gap-1.5">
            {!sidebarOpen ? actionMenu : null}
            <button
              aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-app-muted transition hover:text-app-text focus:outline-none focus-visible:ring-2 focus-visible:ring-app-border-strong"
              onClick={onToggleSidebar}
              type="button"
            >
              <PanelLeftOpen className={`size-4 transition-transform ${sidebarOpen ? "rotate-180" : ""}`} />
            </button>
          </div>
        ) : null}
      </header>

      {dialogState && hasActiveItem ? (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(22,19,16,0.18)] px-4"
          onClick={() => setDialogState(null)}
        >
          <div
            className="w-full max-w-[460px] rounded-[28px] border border-app-border bg-app-panel px-7 py-7 shadow-[0_24px_80px_rgba(34,24,16,0.18)]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="text-[30px] font-semibold tracking-[-0.04em] text-app-text">
              {dialogState.type === "rename" ? `Rename ${itemLabel}` : `Delete ${itemLabel}`}
            </div>

            {dialogState.type === "rename" ? (
              <>
                <div className="mt-5 text-[14px] leading-7 text-app-muted">
                  Give this {itemLabel} a clearer title.
                </div>
                <input
                  autoFocus
                  className="mt-5 w-full rounded-2xl border border-app-border bg-app-panel-strong px-4 py-3 text-[16px] text-app-text outline-none transition focus:border-app-border-strong"
                  onChange={(event) =>
                    setDialogState((current) =>
                      current && current.type === "rename"
                        ? { ...current, value: event.target.value }
                        : current,
                    )
                  }
                  value={dialogState.value}
                />
              </>
            ) : (
              <div className="mt-5 text-[15px] leading-7 text-app-muted">
                Delete <span className="font-semibold text-app-text">{activeItemTitle}</span>? This cannot be undone.
              </div>
            )}

            <div className="mt-7 flex justify-end gap-3">
              <button
                className="rounded-xl px-4 py-2.5 text-[15px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
                onClick={() => setDialogState(null)}
                type="button"
              >
                Cancel
              </button>
              <button
                className={`rounded-xl px-4 py-2.5 text-[15px] font-medium transition ${
                  dialogState.type === "rename"
                    ? "bg-app-accent-soft text-app-accent-strong hover:bg-app-panel-soft"
                    : "bg-[#f7ebe8] text-[#9d3d32] hover:bg-[#f1dfdb]"
                }`}
                onClick={async () => {
                  if (activeItemId === null || activeItemKind === null) {
                    return;
                  }

                  if (dialogState.type === "rename") {
                    const nextTitle = dialogState.value.trim();
                    if (!nextTitle) {
                      return;
                    }
                    await onRenameItem?.(activeItemId, nextTitle, activeItemKind);
                  } else {
                    await onDeleteItem?.(activeItemId, activeItemKind);
                  }

                  setDialogState(null);
                }}
                type="button"
              >
                {dialogState.type === "rename" ? "Rename" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
