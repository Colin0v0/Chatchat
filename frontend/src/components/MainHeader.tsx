import { Download, MoreHorizontal, PanelLeftOpen, Pencil, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { ModelOption } from "../types";
import { ModelSelect } from "./ModelSelect";

interface MainHeaderProps {
  title: string;
  showTitle?: boolean;
  sidebarOpen: boolean;
  isDesktop: boolean;
  mobileModel?: string;
  mobileModels?: ModelOption[];
  activeItemId?: number | null;
  activeItemKind?: "chat" | "debate" | null;
  activeItemTitle?: string;
  onMobileModelChange?: (value: string) => void;
  onExportItem?: (itemId: number, kind: "chat" | "debate") => void | Promise<void>;
  onRenameItem?: (itemId: number, title: string, kind: "chat" | "debate") => void | Promise<void>;
  onDeleteItem?: (itemId: number, kind: "chat" | "debate") => void | Promise<void>;
  onToggleSidebar: () => void;
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
  mobileModel = "",
  mobileModels = [],
  activeItemId = null,
  activeItemKind = null,
  activeItemTitle = "",
  onMobileModelChange,
  onExportItem,
  onRenameItem,
  onDeleteItem,
  onToggleSidebar,
}: MainHeaderProps) {
  const [actionMenuOpen, setActionMenuOpen] = useState(false);
  const [dialogState, setDialogState] = useState<HeaderDialogState>(null);
  const actionMenuRef = useRef<HTMLDivElement | null>(null);
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
            onClick={async () => {
              if (activeItemId === null || activeItemKind === null) {
                return;
              }
              setActionMenuOpen(false);
              await onExportItem?.(activeItemId, activeItemKind);
            }}
            type="button"
          >
            <Download className="size-4 text-[#5f564a]" />
            <span>Export Markdown</span>
          </button>
          <div className="border-t border-app-border/80" role="separator" />
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
        {showTitle ? (
          <div className="flex min-w-0 max-w-[calc(100%-6rem)] items-center gap-1.5 py-1 md:max-w-none">
            <div className="min-w-0 text-[20px] font-semibold leading-none tracking-[-0.04em] text-app-text md:text-[24px]">
              <span className="truncate">{title}</span>
            </div>
            {!isDesktop && mobileModel && mobileModels.length > 0 && onMobileModelChange ? (
              <div className="shrink-0">
                <ModelSelect
                  compact
                  menuPlacement="bottom"
                  model={mobileModel}
                  models={mobileModels}
                  onChange={onMobileModelChange}
                  triggerStyle="chevron"
                />
              </div>
            ) : null}
          </div>
        ) : (
          <div />
        )}

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
