import {
  MessageSquarePlus,
  MoreHorizontal,
  PanelLeftOpen,
  Pencil,
  Search,
  Trash2,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import type { ConversationSummary } from "../types";

interface SidebarProps {
  items: ConversationSummary[];
  activeConversationId: number | null;
  conversationsLoaded: boolean;
  open: boolean;
  isDesktop: boolean;
  query: string;
  onQueryChange: (value: string) => void;
  onNewChat: () => void;
  onRename: (conversationId: number, title: string) => void | Promise<void>;
  onDelete: (conversationId: number) => void | Promise<void>;
  onSelect: (conversationId: number) => void;
  onToggleSidebar: () => void;
}

type SidebarDialogState =
  | {
      type: "rename";
      conversationId: number;
      title: string;
      value: string;
    }
  | {
      type: "delete";
      conversationId: number;
      title: string;
    }
  | null;

interface SidebarActionProps {
  icon: ReactNode;
  label: string;
  isInput?: boolean;
  value?: string;
  alignToRail?: boolean;
  onChange?: (value: string) => void;
  onClick?: () => void;
}

interface DesktopRailProps {
  onNewChat: () => void;
}

interface SidebarContentProps
  extends Omit<SidebarProps, "open" | "isDesktop" | "onToggleSidebar"> {
  alignToRail?: boolean;
}

function SidebarAction({
  icon,
  label,
  isInput = false,
  value = "",
  alignToRail = false,
  onChange,
  onClick,
}: SidebarActionProps) {
  const paddingClass = alignToRail ? "pl-3 pr-4" : "px-4";

  if (isInput) {
    return (
      <label
        className={`flex h-12 items-center gap-3 rounded-[8px] border border-app-border bg-app-panel-strong ${paddingClass} text-app-muted`}
      >
        <span className="shrink-0">{icon}</span>
        <input
          className="w-full bg-transparent text-[15px] placeholder:text-app-muted"
          onChange={(event) => onChange?.(event.target.value)}
          placeholder={label}
          value={value}
        />
      </label>
    );
  }

  return (
    <button
      className={`flex h-12 items-center gap-3 rounded-[8px] border border-app-border bg-app-panel-strong ${paddingClass} text-[15px] font-medium tracking-[-0.02em] text-app-text transition hover:bg-app-panel-soft`}
      onClick={onClick}
      type="button"
    >
      <span className="shrink-0 text-app-muted">{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function RailButton({
  icon,
  label,
  showTooltip = true,
  alignWithAction = false,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  showTooltip?: boolean;
  alignWithAction?: boolean;
  onClick?: () => void;
}) {
  const sizeClass = alignWithAction ? "h-12 w-9" : "h-9 w-9";

  return (
    <div className="group relative flex items-center">
      <button
        aria-label={label}
        className={`flex ${sizeClass} items-center justify-center rounded-[8px] text-app-muted transition hover:text-app-text`}
        onClick={onClick}
        type="button"
      >
        {icon}
      </button>

      {showTooltip ? (
        <div className="pointer-events-none absolute left-[calc(100%+10px)] top-1/2 z-30 -translate-y-1/2 whitespace-nowrap rounded-lg bg-app-accent px-3 py-2 text-[13px] font-medium text-white opacity-0 shadow-[0_10px_24px_rgba(59,43,28,0.18)] transition duration-150 group-hover:opacity-100">
          <span>{label}</span>
        </div>
      ) : null}
    </div>
  );
}

function DesktopRail({ onNewChat }: DesktopRailProps) {
  return (
    <div className="flex h-full flex-col bg-app-sidebar px-2 py-4">
      <div className="flex h-9 items-center justify-center">
        <div className="flex h-9 w-9 items-center justify-center text-[18px] font-semibold text-app-accent-strong">
          C
        </div>
      </div>

      <div className="mt-4 flex justify-center">
        <RailButton
          alignWithAction
          icon={<MessageSquarePlus className="size-4" />}
          label="New chat"
          onClick={onNewChat}
        />
      </div>
    </div>
  );
}

function SidebarDialog({
  state,
  onCancel,
  onConfirmRename,
  onConfirmDelete,
  onRenameValueChange,
}: {
  state: SidebarDialogState;
  onCancel: () => void;
  onConfirmRename: () => void | Promise<void>;
  onConfirmDelete: () => void | Promise<void>;
  onRenameValueChange: (value: string) => void;
}) {
  if (!state) {
    return null;
  }

  const isRename = state.type === "rename";

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(22,19,16,0.18)] px-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-[460px] rounded-[28px] border border-app-border bg-app-panel px-7 py-7 shadow-[0_24px_80px_rgba(34,24,16,0.18)]"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="text-[30px] font-semibold tracking-[-0.04em] text-app-text">
          {isRename ? "Rename chat" : "Delete chat"}
        </div>

        {isRename ? (
          <>
            <div className="mt-5 text-[14px] leading-7 text-app-muted">
              Give this chat a clearer title.
            </div>
            <input
              autoFocus
              className="mt-5 w-full rounded-2xl border border-app-border bg-app-panel-strong px-4 py-3 text-[16px] text-app-text outline-none transition focus:border-app-border-strong"
              onChange={(event) => onRenameValueChange(event.target.value)}
              value={state.value}
            />
          </>
        ) : (
          <div className="mt-5 text-[15px] leading-7 text-app-muted">
            Delete <span className="font-semibold text-app-text">{state.title}</span>? This cannot be undone.
          </div>
        )}

        <div className="mt-7 flex justify-end gap-3">
          <button
            className="rounded-xl px-4 py-2.5 text-[15px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
            onClick={onCancel}
            type="button"
          >
            Cancel
          </button>
          <button
            className={`rounded-xl px-4 py-2.5 text-[15px] font-medium transition ${
              isRename
                ? "bg-app-accent-soft text-app-accent-strong hover:bg-app-panel-soft"
                : "bg-[#f7ebe8] text-[#9d3d32] hover:bg-[#f1dfdb]"
            }`}
            onClick={isRename ? onConfirmRename : onConfirmDelete}
            type="button"
          >
            {isRename ? "Rename" : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}

function SidebarLoadingState() {
  return (
    <div className="flex min-h-full w-full items-start justify-center pt-[25%]">
      <div className="inline-flex items-center gap-2.5 px-3 py-2 text-[14px] text-app-muted/85">
        <span className="animate-[thinking-dot_1.8s_ease-in-out_infinite] tracking-[0.02em]">
          Loading
        </span>
        <span aria-hidden="true" className="inline-flex items-center gap-1.5 self-center">
          <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.15s_infinite]" />
          <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.3s_infinite]" />
          <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.45s_infinite]" />
        </span>
      </div>
    </div>
  );
}

function SidebarContent({
  items,
  activeConversationId,
  conversationsLoaded,
  query,
  onQueryChange,
  onNewChat,
  onRename,
  onDelete,
  onSelect,
  alignToRail = false,
}: SidebarContentProps) {
  const [menuConversationId, setMenuConversationId] = useState<number | null>(null);
  const [dialogState, setDialogState] = useState<SidebarDialogState>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const horizontalPadding = alignToRail ? "px-2" : "px-4";
  const sectionPadding = alignToRail ? "px-2" : "px-4";
  const headingPadding = alignToRail ? "px-3" : "px-4";

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (dialogState) {
        return;
      }
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuConversationId(null);
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
      <div className="flex h-full flex-col gap-4 bg-app-sidebar py-4">
        <div className={`flex min-w-0 items-center gap-3 ${horizontalPadding} -mt-0.5`}>
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-app-accent-soft text-[18px] font-semibold text-app-accent-strong">
            C
          </div>
          <div className="min-w-0">
            <div className="truncate text-[15px] font-semibold tracking-[-0.02em]">
              Chatchat
            </div>
            <div className="truncate text-[13px] tracking-[0.08em] text-app-muted lowercase">
              reasoning workspace
            </div>
          </div>
        </div>

        <div className={`flex flex-col gap-3 ${sectionPadding}`}>
          <SidebarAction
            alignToRail={alignToRail}
            icon={<MessageSquarePlus className="size-4" />}
            label="New chat"
            onClick={onNewChat}
          />
          <SidebarAction
            alignToRail={alignToRail}
            icon={<Search className="size-4" />}
            isInput
            label="Search chats"
            onChange={onQueryChange}
            value={query}
          />
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-3">
          <div className={`${headingPadding} text-[13px] font-semibold tracking-[0.14em] text-app-muted uppercase`}>
            Recent
          </div>

          <div className="app-scrollbar app-scrollbar-sidebar min-h-0 flex-1 overflow-y-auto">
            {!conversationsLoaded ? (
              <div className={sectionPadding}>
                <SidebarLoadingState />
              </div>
            ) : null}

            {conversationsLoaded ? (
              <div className={`flex flex-col gap-2 ${sectionPadding}`}>
                {items.length === 0 ? (
                  <div className="px-3 py-2 text-[14px] text-app-muted">
                    还没有对话，先发第一条消息。
                  </div>
                ) : null}

                {items.map((item) => {
                  const active = item.id === activeConversationId;
                  return (
                    <div
                      className={`group relative rounded-[8px] transition ${
                        active
                          ? "bg-app-panel-strong shadow-[0_6px_18px_rgba(34,24,16,0.06)]"
                          : "hover:bg-app-panel-soft"
                      }`}
                      key={item.id}
                    >
                      <button
                        className="flex w-full min-w-0 items-center rounded-[8px] px-3 py-3 pr-11 text-left"
                        onClick={() => onSelect(item.id)}
                        type="button"
                      >
                        <span className="truncate text-[15px] font-semibold tracking-[-0.02em] text-app-text">
                          {item.title}
                        </span>
                      </button>

                      <div
                        className="absolute inset-y-0 right-2 flex items-center"
                        ref={menuConversationId === item.id ? menuRef : null}
                      >
                        <button
                          aria-label="Conversation actions"
                          className={`flex h-8 w-8 items-center justify-center rounded-[8px] text-app-muted transition hover:text-app-text ${
                            menuConversationId === item.id ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                          }`}
                          onClick={(event) => {
                            event.stopPropagation();
                            setMenuConversationId((current) =>
                              current === item.id ? null : item.id,
                            );
                          }}
                          type="button"
                        >
                          <MoreHorizontal className="size-4" />
                        </button>

                        {menuConversationId === item.id ? (
                          <div className="absolute right-0 top-[calc(100%+6px)] z-30 overflow-hidden rounded-[8px] border border-app-border bg-app-panel-strong py-1.5 shadow-[0_16px_40px_rgba(34,24,16,0.12)]">
                            <button
                              className="flex items-center gap-2 whitespace-nowrap px-4 py-2.5 text-left text-[14px] text-app-text transition hover:text-app-accent-strong"
                              onClick={(event) => {
                                event.stopPropagation();
                                setMenuConversationId(null);
                                setDialogState({
                                  type: "rename",
                                  conversationId: item.id,
                                  title: item.title,
                                  value: item.title,
                                });
                              }}
                              type="button"
                            >
                              <Pencil className="size-4 text-app-muted" />
                              <span>Rename</span>
                            </button>
                            <button
                              className="flex items-center gap-2 whitespace-nowrap px-4 py-2.5 text-left text-[14px] text-[#9d3d32] transition hover:text-[#8a3329]"
                              onClick={(event) => {
                                event.stopPropagation();
                                setMenuConversationId(null);
                                setDialogState({
                                  type: "delete",
                                  conversationId: item.id,
                                  title: item.title,
                                });
                              }}
                              type="button"
                            >
                              <Trash2 className="size-4" />
                              <span>Delete</span>
                            </button>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : null}
          </div>
        </div>
      </div>
      <SidebarDialog
        onCancel={() => setDialogState(null)}
        onConfirmDelete={async () => {
          if (!dialogState || dialogState.type !== "delete") {
            return;
          }
          await onDelete(dialogState.conversationId);
          setDialogState(null);
        }}
        onConfirmRename={async () => {
          if (!dialogState || dialogState.type !== "rename") {
            return;
          }
          const nextTitle = dialogState.value.trim();
          if (!nextTitle) {
            return;
          }
          await onRename(dialogState.conversationId, nextTitle);
          setDialogState(null);
        }}
        onRenameValueChange={(value) => {
          setDialogState((current) =>
            current && current.type === "rename" ? { ...current, value } : current,
          );
        }}
        state={dialogState}
      />
    </>
  );
}

function DesktopSidebarToggle({
  open,
  onToggle,
}: {
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      aria-label={open ? "Collapse sidebar" : "Expand sidebar"}
      className="absolute bottom-4 left-[10px] z-20 flex h-9 w-9 items-center justify-center rounded-[8px] text-app-muted transition hover:text-app-text"
      onClick={onToggle}
      type="button"
    >
      <PanelLeftOpen className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} />
    </button>
  );
}

export function Sidebar({
  items,
  activeConversationId,
  conversationsLoaded,
  open,
  isDesktop,
  query,
  onQueryChange,
  onNewChat,
  onRename,
  onDelete,
  onSelect,
  onToggleSidebar,
}: SidebarProps) {
  const contentProps = {
    items,
    activeConversationId,
    conversationsLoaded,
    query,
    onQueryChange,
    onNewChat,
    onRename,
    onDelete,
    onSelect,
  };

  return (
    <>
      <div
        className={`relative hidden h-full overflow-visible border-r border-app-border bg-app-sidebar transition-[width] duration-300 ease-out md:block ${
          open ? "w-[280px]" : "w-[56px]"
        }`}
      >
        {open ? <SidebarContent {...contentProps} alignToRail /> : <DesktopRail onNewChat={onNewChat} />}
        <DesktopSidebarToggle onToggle={onToggleSidebar} open={open} />
      </div>

      <div
        className={`fixed inset-y-0 right-0 z-20 w-[280px] transform transition-transform duration-300 ease-out md:hidden ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="h-full border-l border-app-border bg-app-sidebar shadow-[0_0_0_1px_rgba(0,0,0,0.03)]">
          <SidebarContent {...contentProps} />
        </div>
      </div>

      {!isDesktop ? (
        <div
          aria-hidden={open ? undefined : true}
          className={`fixed inset-0 z-10 bg-black/10 transition-opacity duration-300 md:hidden ${
            open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
          }`}
          onClick={onToggleSidebar}
        />
      ) : null}
    </>
  );
}

