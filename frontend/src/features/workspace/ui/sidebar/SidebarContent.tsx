import { LoaderCircle, MessageSquare, MoreHorizontal, Pencil, Scale, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  MobileSidebarFooter,
  SidebarBrand,
  SidebarIcon,
  SidebarLoadingState,
  SidebarTooltip,
} from "./SidebarActions";
import { SidebarDialog } from "./SidebarDialog";
import { SIDEBAR_PRIMARY_ITEMS } from "./navigation";
import { cn, sidebarMenuItemClass, sidebarMenuPanelClass } from "./styles";
import type { SidebarDialogState, SidebarSharedProps } from "./types";

interface SidebarContentProps extends SidebarSharedProps {
  mode: "desktop" | "mobile";
  open?: boolean;
}

const DESKTOP_SIDEBAR_COLLAPSE_MS = 300;

type CombinedSidebarItem =
  | {
      kind: "chat";
      id: number;
      title: string;
      updatedAt: string | null;
    }
  | {
      kind: "debate";
      id: number;
      title: string;
      updatedAt: string | null;
    };

export function SidebarContent({
  items,
  debateItems,
  activity = {},
  activeSection,
  activeConversationId,
  activeDebateId,
  conversationsLoaded,
  debatesLoaded,
  query,
  onRename,
  onDelete,
  onRenameDebate,
  onDeleteDebate,
  onLogout,
  onOpenSearch,
  onSelect,
  onSelectDebate,
  onSelectSection,
  viewerName,
  mode,
  open = true,
}: SidebarContentProps) {
  const [menuItemKey, setMenuItemKey] = useState<string | null>(null);
  const [dialogState, setDialogState] = useState<SidebarDialogState>(null);
  const [collapsedPrimaryNavReady, setCollapsedPrimaryNavReady] = useState(mode === "desktop" && !open);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const isDesktop = mode === "desktop";
  const useCollapsedPrimaryNavLayout = isDesktop && !open && collapsedPrimaryNavReady;
  const showDesktopText = !isDesktop || open;
  const showSecondaryContent = !isDesktop || open;
  const sectionPadding = isDesktop ? "px-2" : "px-4";
  const headingPadding = isDesktop ? "px-5" : "px-4";
  const contentTopPadding = isDesktop ? "pt-[50px]" : "pt-4";
  const contentBottomPadding = isDesktop ? "pb-[48px]" : "pb-4";
  const conversationMenuBufferHeight = isDesktop ? "h-[136px]" : "h-0";
  const emptyText = query.trim()
    ? "No sessions matched your search."
    : "还没有任何会话，先新建聊天或发起辩论。";
  const combinedItems = useMemo<CombinedSidebarItem[]>(() => {
    const chatItems: CombinedSidebarItem[] = items.map((item) => ({
      kind: "chat",
      id: item.id,
      title: item.title,
      updatedAt: item.updated_at,
    }));
    const mergedDebates: CombinedSidebarItem[] = debateItems.map((item) => ({
      kind: "debate",
      id: item.id,
      title: item.topic,
      updatedAt: item.updated_at,
    }));

    return [...chatItems, ...mergedDebates].sort((left, right) => {
      const leftTime = left.updatedAt ? Date.parse(left.updatedAt) : 0;
      const rightTime = right.updatedAt ? Date.parse(right.updatedAt) : 0;
      return rightTime - leftTime;
    });
  }, [debateItems, items]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (dialogState) {
        return;
      }
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuItemKey(null);
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

  useEffect(() => {
    if (!isDesktop) {
      setCollapsedPrimaryNavReady(false);
      return;
    }

    if (open) {
      setCollapsedPrimaryNavReady(false);
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setCollapsedPrimaryNavReady(true);
    }, DESKTOP_SIDEBAR_COLLAPSE_MS);

    return () => window.clearTimeout(timeoutId);
  }, [isDesktop, open]);

  return (
    <>
      <div className={`flex h-full flex-col bg-app-sidebar ${contentTopPadding} ${contentBottomPadding}`}>
        {isDesktop ? null : (
          <div className="flex min-w-0 flex-col gap-4 px-4">
            <SidebarBrand title={viewerName || "Chatchat"} />
          </div>
        )}

        <div className="mt-4 flex min-h-0 flex-1 flex-col gap-2">
          <div className={`flex flex-col gap-1 ${sectionPadding}`}>
            {SIDEBAR_PRIMARY_ITEMS.map((item) => {
              const isActive = item.kind === "section" && item.section === activeSection;
              return (
                <div className="group relative" key={item.label}>
                  <button
                    className={cn(
                      "relative flex min-h-[38.5px] w-full items-center overflow-hidden rounded-[8px] px-3 text-left text-[15px] font-medium tracking-[-0.02em] text-app-text transition-colors",
                      showDesktopText ? "hover:bg-app-panel-soft" : "hover:bg-app-panel-soft",
                      isActive && "bg-app-panel-soft",
                    )}
                    onClick={() => {
                      if (item.kind === "action") {
                        onOpenSearch();
                        return;
                      }
                      onSelectSection(item.section);
                    }}
                    type="button"
                  >
                    <span
                      className={cn(
                        "absolute inset-y-0 flex items-center justify-center text-app-text",
                        useCollapsedPrimaryNavLayout ? "inset-x-0" : "left-3",
                      )}
                    >
                      <SidebarIcon icon={item.icon} />
                    </span>
                    <span
                      className={cn(
                        "min-w-0 overflow-hidden whitespace-nowrap",
                        showDesktopText
                          ? "max-w-[160px] pl-7 opacity-100"
                          : "pointer-events-none max-w-0 pl-0 opacity-0",
                      )}
                    >
                      <span className="truncate">{item.label}</span>
                    </span>
                  </button>
                  {useCollapsedPrimaryNavLayout ? <SidebarTooltip label={item.label} /> : null}
                </div>
              );
            })}
          </div>

          {showSecondaryContent ? (
            <>
              <div className={cn(headingPadding, "text-[13px] font-semibold tracking-[0.14em] text-app-muted uppercase")}>
                Recents
              </div>

              <div className="app-scrollbar app-scrollbar-sidebar min-h-0 flex-1 overflow-y-auto">
                {!conversationsLoaded || !debatesLoaded ? (
                  <div className={sectionPadding}>
                    <SidebarLoadingState />
                  </div>
                ) : null}

                {conversationsLoaded && debatesLoaded ? (
                  <div className={`flex flex-col gap-1 ${sectionPadding}`}>
                    {combinedItems.length === 0 ? (
                      <div className="overflow-hidden px-3 py-2 text-[14px] text-app-muted">{emptyText}</div>
                    ) : null}

                    {combinedItems.map((item) => {
                      const active =
                        item.kind === "chat"
                          ? activeSection === "chats" && item.id === activeConversationId
                          : activeSection === "debates" && item.id === activeDebateId;
                      const itemActivity = item.kind === "chat" ? activity[item.id] : undefined;
                      const itemKey = `${item.kind}:${item.id}`;

                      return (
                        <div
                          className={cn(
                            "group relative rounded-[8px] transition-colors",
                            active
                              ? "bg-app-panel-soft"
                              : "hover:bg-app-panel-soft",
                          )}
                          key={itemKey}
                        >
                          <button
                            className="flex w-full min-w-0 items-center rounded-[8px] px-3 py-2 pr-12 text-left focus:outline-none focus-visible:outline-none"
                            onClick={() => (item.kind === "chat" ? onSelect(item.id) : onSelectDebate(item.id))}
                            type="button"
                          >
                            <span className="flex min-w-0 items-center gap-2.5">
                              {item.kind === "debate" ? (
                                <Scale className="size-4 shrink-0 text-app-muted" />
                              ) : (
                                <MessageSquare className="size-4 shrink-0 text-app-muted" />
                              )}
                              <span className="truncate text-[15px] font-semibold tracking-[-0.02em] text-app-text">
                                {item.title}
                              </span>
                              {itemActivity?.running ? (
                                <span
                                  aria-label="Conversation is running"
                                  className="flex h-5 w-5 shrink-0 items-center justify-center text-app-muted"
                                >
                                  <LoaderCircle className="size-3.5 animate-spin" />
                                </span>
                              ) : itemActivity?.unread ? (
                                <span
                                  aria-label="Conversation has a new response"
                                  className="inline-flex h-2.5 w-2.5 shrink-0 rounded-full bg-app-accent-strong"
                                />
                              ) : null}
                            </span>
                          </button>

                          <div
                            className="absolute inset-y-0 right-2 flex items-center"
                            ref={menuItemKey === itemKey ? menuRef : null}
                          >
                            {isDesktop ? (
                              <>
                                <button
                                  aria-label="Session actions"
                                  className={cn(
                                    "flex h-8 w-8 items-center justify-center rounded-[8px] text-app-muted transition-colors",
                                    "hover:text-app-text focus:outline-none focus-visible:outline-none",
                                    menuItemKey === itemKey ? "opacity-100" : "opacity-0 group-hover:opacity-100",
                                  )}
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    setMenuItemKey((current) => (current === itemKey ? null : itemKey));
                                  }}
                                  type="button"
                                >
                                  <MoreHorizontal className="size-4" />
                                </button>

                                {menuItemKey === itemKey ? (
                                  <div className={`absolute right-0 top-[calc(100%+6px)] z-30 py-1 ${sidebarMenuPanelClass}`}>
                                    <button
                                      className={`${sidebarMenuItemClass} text-app-text hover:text-app-accent-strong`}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        setMenuItemKey(null);
                                        setDialogState({
                                          type: "rename",
                                          kind: item.kind,
                                          id: item.id,
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
                                      className={`${sidebarMenuItemClass} text-[#9d3d32] hover:text-[#8a3329]`}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        setMenuItemKey(null);
                                        setDialogState({
                                          type: "delete",
                                          kind: item.kind,
                                          id: item.id,
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
                              </>
                            ) : null}
                          </div>
                        </div>
                      );
                    })}

                    {combinedItems.length > 0 ? <div aria-hidden="true" className={conversationMenuBufferHeight} /> : null}
                  </div>
                ) : null}
              </div>
            </>
          ) : null}
        </div>

        {!isDesktop ? <MobileSidebarFooter onLogout={onLogout} /> : null}
      </div>

      <SidebarDialog
        onCancel={() => setDialogState(null)}
        onConfirmDelete={async () => {
          if (!dialogState || dialogState.type !== "delete") {
            return;
          }

          if (dialogState.kind === "debate") {
            await onDeleteDebate(dialogState.id);
          } else {
            await onDelete(dialogState.id);
          }
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

          if (dialogState.kind === "debate") {
            await onRenameDebate(dialogState.id, nextTitle);
          } else {
            await onRename(dialogState.id, nextTitle);
          }
          setDialogState(null);
        }}
        onRenameValueChange={(value) =>
          setDialogState((current) =>
            current && current.type === "rename" ? { ...current, value } : current,
          )
        }
        state={dialogState}
      />
    </>
  );
}
