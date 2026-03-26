import { MessageSquarePlus, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Search, SidebarAction, SidebarBrand, SidebarIcon, SidebarLoadingState } from "./SidebarActions";
import { SidebarDialog } from "./SidebarDialog";
import { cn, sidebarMenuItemClass, sidebarMenuPanelClass } from "./styles";
import type { SidebarDialogState, SidebarSharedProps } from "./types";

interface SidebarContentProps extends SidebarSharedProps {
  mode: "desktop" | "mobile";
}

export function SidebarContent({
  items,
  activeConversationId,
  conversationsLoaded,
  query,
  onQueryChange,
  onNewChat,
  onRename,
  onDelete,
  onSelect,
  mode,
}: SidebarContentProps) {
  const [menuConversationId, setMenuConversationId] = useState<number | null>(null);
  const [dialogState, setDialogState] = useState<SidebarDialogState>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const isDesktop = mode === "desktop";
  const sectionPadding = isDesktop ? "px-2" : "px-4";
  const headingPadding = isDesktop ? "px-3" : "px-4";
  const contentTopPadding = isDesktop ? "pt-[132px]" : "pt-4";
  const emptyText = "\u8fd8\u6ca1\u6709\u5bf9\u8bdd\uff0c\u5148\u53d1\u7b2c\u4e00\u6761\u6d88\u606f\u3002";

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
      <div className={`flex h-full flex-col bg-app-sidebar ${contentTopPadding} pb-4`}>
        {isDesktop ? (
          <div className={sectionPadding}>
            <SidebarAction
              alignToRail
              icon={<SidebarIcon icon={Search} />}
              isInput
              label="Search chats"
              onChange={onQueryChange}
              value={query}
            />
          </div>
        ) : (
          <div className="flex min-w-0 flex-col gap-4 px-4">
            <SidebarBrand />
            <div className="flex flex-col gap-3">
              <SidebarAction
                icon={<MessageSquarePlus className="size-4" />}
                label="New chat"
                onClick={onNewChat}
              />
              <SidebarAction
                icon={<SidebarIcon icon={Search} />}
                isInput
                label="Search chats"
                onChange={onQueryChange}
                value={query}
              />
            </div>
          </div>
        )}

        <div className="mt-4 flex min-h-0 flex-1 flex-col gap-3">
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
                  <div className="px-3 py-2 text-[14px] text-app-muted">{emptyText}</div>
                ) : null}

                {items.map((item) => {
                  const active = item.id === activeConversationId;

                  return (
                    <div
                      className={cn(
                        "group relative rounded-[8px] transition-colors",
                        active
                          ? "bg-app-panel-strong shadow-[0_6px_18px_rgba(34,24,16,0.06)]"
                          : "hover:bg-app-panel-soft",
                      )}
                      key={item.id}
                    >
                      <button
                        className="flex w-full min-w-0 items-center rounded-[8px] px-3 py-3 pr-11 text-left focus:outline-none focus-visible:outline-none"
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
                          className={cn(
                            "flex h-8 w-8 items-center justify-center rounded-[8px] text-app-muted transition-colors",
                            "hover:text-app-text focus:outline-none focus-visible:outline-none",
                            menuConversationId === item.id ? "opacity-100" : "opacity-0 group-hover:opacity-100",
                          )}
                          onClick={(event) => {
                            event.stopPropagation();
                            setMenuConversationId((current) => (current === item.id ? null : item.id));
                          }}
                          type="button"
                        >
                          <MoreHorizontal className="size-4" />
                        </button>

                        {menuConversationId === item.id ? (
                          <div className={`absolute right-0 top-[calc(100%+6px)] z-30 py-1 ${sidebarMenuPanelClass}`}>
                            <button
                              className={`${sidebarMenuItemClass} text-app-text hover:text-app-accent-strong`}
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
                              className={`${sidebarMenuItemClass} text-[#9d3d32] hover:text-[#8a3329]`}
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