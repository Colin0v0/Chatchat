import { MoreHorizontal, PanelLeftOpen, Pencil, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface MainHeaderProps {
  title: string;
  showTitle?: boolean;
  sidebarOpen: boolean;
  isDesktop: boolean;
  conversationId?: number | null;
  conversationTitle?: string;
  onRenameConversation?: (conversationId: number, title: string) => void | Promise<void>;
  onDeleteConversation?: (conversationId: number) => void | Promise<void>;
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
  conversationId = null,
  conversationTitle = "",
  onRenameConversation,
  onDeleteConversation,
  onToggleSidebar,
}: MainHeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [dialogState, setDialogState] = useState<HeaderDialogState>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const hasConversation = conversationId !== null;

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (dialogState) {
        return;
      }
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
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

  return (
    <>
      <header className="relative flex h-[68px] items-center justify-between px-4 md:px-6">
        {showTitle ? (
          <div className="truncate text-[20px] font-semibold leading-none tracking-[-0.04em] md:text-[24px]">
            {title}
          </div>
        ) : (
          <div />
        )}

        {isDesktop && hasConversation ? (
          <div className="relative" ref={menuRef}>
            <button
              aria-label="Conversation actions"
              className="flex h-8 w-8 items-center justify-center rounded-[8px] text-app-muted transition hover:text-app-text"
              onClick={() => setMenuOpen((value) => !value)}
              type="button"
            >
              <MoreHorizontal className="size-4" />
            </button>

            {menuOpen ? (
              <div className="absolute right-0 top-[calc(100%+6px)] z-30 overflow-hidden rounded-[8px] border border-app-border bg-app-panel-strong py-1.5 shadow-[0_16px_40px_rgba(34,24,16,0.12)]">
                <button
                  className="flex items-center gap-2 whitespace-nowrap px-4 py-2.5 text-left text-[14px] text-app-text transition hover:text-app-accent-strong"
                  onClick={() => {
                    setMenuOpen(false);
                    setDialogState({
                      type: "rename",
                      value: conversationTitle,
                    });
                  }}
                  type="button"
                >
                  <Pencil className="size-4 text-app-muted" />
                  <span>Rename</span>
                </button>
                <button
                  className="flex items-center gap-2 whitespace-nowrap px-4 py-2.5 text-left text-[14px] text-[#9d3d32] transition hover:text-[#8a3329]"
                  onClick={() => {
                    setMenuOpen(false);
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
        ) : null}

        {!isDesktop ? (
          <button
            aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            className="fixed top-4 right-4 z-30 flex h-9 w-9 items-center justify-center rounded-lg text-app-muted transition hover:text-app-text focus:outline-none focus-visible:ring-2 focus-visible:ring-app-border-strong"
            onClick={onToggleSidebar}
            type="button"
          >
            <PanelLeftOpen className={`size-4 transition-transform ${sidebarOpen ? "rotate-180" : ""}`} />
          </button>
        ) : null}
      </header>

      {dialogState && hasConversation ? (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(22,19,16,0.18)] px-4"
          onClick={() => setDialogState(null)}
        >
          <div
            className="w-full max-w-[460px] rounded-[28px] border border-app-border bg-app-panel px-7 py-7 shadow-[0_24px_80px_rgba(34,24,16,0.18)]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="text-[30px] font-semibold tracking-[-0.04em] text-app-text">
              {dialogState.type === "rename" ? "Rename chat" : "Delete chat"}
            </div>

            {dialogState.type === "rename" ? (
              <>
                <div className="mt-5 text-[14px] leading-7 text-app-muted">
                  Give this chat a clearer title.
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
                Delete <span className="font-semibold text-app-text">{conversationTitle}</span>? This cannot be undone.
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
                  if (conversationId === null) {
                    return;
                  }

                  if (dialogState.type === "rename") {
                    const nextTitle = dialogState.value.trim();
                    if (!nextTitle) {
                      return;
                    }
                    await onRenameConversation?.(conversationId, nextTitle);
                  } else {
                    await onDeleteConversation?.(conversationId);
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
