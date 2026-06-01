import { FolderKanban, LoaderCircle, MessageSquare, MoreHorizontal, Pencil, Plus, Scale, Swords, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
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
    }
  | {
      kind: "battle";
      id: number;
      title: string;
      updatedAt: string | null;
    };

export function SidebarContent({
  items,
  debateItems,
  battleItems,
  activity = {},
  debateActivity = {},
  activeSection,
  activeConversationId,
  activeDebateId,
  activeBattleId,
  activeProjectId,
  battlesLoaded,
  conversationsLoaded,
  debatesLoaded,
  projectIsSaving,
  projects,
  projectsLoaded,
  query,
  onRename,
  onDelete,
  onRenameDebate,
  onDeleteDebate,
  onRenameBattle,
  onDeleteBattle,
  onOpenSearch,
  onSelect,
  onSelectDebate,
  onSelectBattle,
  onSelectProject,
  onCreateProject,
  onSelectSection,
  mode,
  open = true,
}: SidebarContentProps) {
  const [menuItemKey, setMenuItemKey] = useState<string | null>(null);
  const [dialogState, setDialogState] = useState<SidebarDialogState>(null);
  const [projectCreateOpen, setProjectCreateOpen] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [collapsedPrimaryNavReady, setCollapsedPrimaryNavReady] = useState(mode === "desktop" && !open);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const isDesktop = mode === "desktop";
  const useCollapsedPrimaryNavLayout = isDesktop && !open && collapsedPrimaryNavReady;
  const showDesktopText = !isDesktop || open;
  const showSecondaryContent = !isDesktop || open;
  const sectionPadding = isDesktop ? "px-2" : "px-3";
  const headingPadding = isDesktop ? "px-5" : "px-3";
  const conversationMenuBufferHeight = isDesktop ? "h-[136px]" : "h-0";
  const emptyText = query.trim()
    ? "No sessions matched your search."
    : "还没有任何会话，快去创建一个吧！";
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
    const mergedBattles: CombinedSidebarItem[] = battleItems.map((item) => ({
      kind: "battle",
      id: item.id,
      title: item.title,
      updatedAt: item.updated_at,
    }));

    return [...chatItems, ...mergedDebates, ...mergedBattles].sort((left, right) => {
      const leftTime = left.updatedAt ? Date.parse(left.updatedAt) : 0;
      const rightTime = right.updatedAt ? Date.parse(right.updatedAt) : 0;
      return rightTime - leftTime;
    });
  }, [battleItems, debateItems, items]);

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
      <div className="flex h-full min-h-0 flex-col bg-app-sidebar">
        <div className={cn("flex shrink-0 flex-col gap-2", isDesktop ? "pt-3" : "pt-1")}>
          <div className={`flex flex-col gap-1 ${sectionPadding}`}>
            {showDesktopText ? (
              <div className="flex items-center gap-2 rounded-[8px] border border-app-border bg-app-panel-strong px-2.5 py-2">
                <FolderKanban className="size-4 shrink-0 text-app-muted" />
                <select
                  aria-label="Project space"
                  className="min-w-0 flex-1 bg-transparent text-[14px] font-semibold text-app-text outline-none"
                  disabled={!projectsLoaded}
                  onChange={(event) => {
                    const nextProjectId = event.target.value ? Number(event.target.value) : null;
                    onSelectProject(nextProjectId);
                  }}
                  value={activeProjectId ?? ""}
                >
                  <option value="">全部项目</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
                <button
                  aria-label="新建项目"
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
                  disabled={projectIsSaving}
                  onClick={() => {
                    setProjectName("");
                    setProjectCreateOpen(true);
                  }}
                  type="button"
                >
                  {projectIsSaving ? <LoaderCircle className="size-3.5 animate-spin" /> : <Plus className="size-4" />}
                </button>
              </div>
            ) : (
              <div className="group relative">
                <button
                  aria-label="项目空间"
                  className="flex min-h-[38.5px] w-full items-center justify-center rounded-[8px] text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
                  onClick={() => {
                    setProjectName("");
                    setProjectCreateOpen(true);
                  }}
                  type="button"
                >
                  <FolderKanban className="size-4" />
                </button>
                {useCollapsedPrimaryNavLayout ? <SidebarTooltip label="项目空间" /> : null}
              </div>
            )}
          </div>

          <div className={`flex flex-col gap-1 ${sectionPadding}`}>
            {SIDEBAR_PRIMARY_ITEMS.map((item) => {
              const isActive = item.kind === "section" && item.section === activeSection;
              return (
                <div className="group relative" key={item.label}>
                  <button
                    className={cn(
                      "relative flex min-h-[38.5px] w-full items-center overflow-hidden rounded-[8px] text-left text-[15px] font-medium tracking-[-0.02em] text-app-text transition-colors",
                      isDesktop ? "px-3" : "px-0",
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
                        useCollapsedPrimaryNavLayout ? "inset-x-0" : isDesktop ? "left-3" : "left-0",
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
        </div>

        {showSecondaryContent ? (
          <>
            <div className={cn("shrink-0 pt-3", headingPadding, "text-[13px] font-semibold tracking-[0.14em] text-app-muted uppercase")}>
              Recents
            </div>

            <div className="sidebar-scrollbar-hidden min-h-0 flex-1 overflow-x-hidden overflow-y-auto pt-2">
              {!conversationsLoaded || !debatesLoaded || !battlesLoaded ? (
                <div className={sectionPadding}>
                  <SidebarLoadingState />
                </div>
              ) : null}

              {conversationsLoaded && debatesLoaded && battlesLoaded ? (
                <div className={`flex flex-col gap-1 ${sectionPadding}`}>
                  {combinedItems.length === 0 ? (
                    <div className="overflow-hidden px-3 py-2 text-[14px] text-app-muted">{emptyText}</div>
                  ) : null}

                  {combinedItems.map((item) => {
                    const active =
                      item.kind === "chat"
                        ? activeSection === "chats" && item.id === activeConversationId
                        : item.kind === "debate"
                          ? activeSection === "debates" && item.id === activeDebateId
                          : activeSection === "battle" && item.id === activeBattleId;
                    const itemActivity =
                      item.kind === "chat"
                        ? activity[item.id]
                        : item.kind === "debate"
                          ? debateActivity[item.id]
                          : undefined;
                    const showActivityIndicator = !active && !!itemActivity && (itemActivity.running || itemActivity.unread);
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
                          className={cn(
                            "flex w-full min-w-0 items-center rounded-[8px] py-2 pr-12 text-left focus:outline-none focus-visible:outline-none",
                            isDesktop ? "px-3" : "px-0",
                          )}
                          onClick={() => {
                            if (item.kind === "chat") {
                              onSelect(item.id);
                              return;
                            }
                            if (item.kind === "debate") {
                              onSelectDebate(item.id);
                              return;
                            }
                            onSelectBattle(item.id);
                          }}
                          type="button"
                        >
                          <span className="flex min-w-0 items-center gap-2.5">
                            {item.kind === "battle" ? (
                              <Swords className="size-4 shrink-0 text-app-muted" />
                            ) : item.kind === "debate" ? (
                              <Scale className="size-4 shrink-0 text-app-muted" />
                            ) : (
                              <MessageSquare className="size-4 shrink-0 text-app-muted" />
                            )}
                            <span className="truncate text-[15px] font-semibold tracking-[-0.02em] text-app-text">
                              {item.title}
                            </span>
                            {showActivityIndicator && itemActivity?.running ? (
                              <span
                                aria-label={`${item.kind === "chat" ? "Conversation" : item.kind === "debate" ? "Debate" : "Battle"} is running`}
                                className="flex h-5 w-5 shrink-0 items-center justify-center text-app-muted"
                              >
                                <LoaderCircle className="size-3.5 animate-spin" />
                              </span>
                            ) : showActivityIndicator && itemActivity?.unread ? (
                              <span
                                aria-label={`${item.kind === "chat" ? "Conversation" : item.kind === "debate" ? "Debate" : "Battle"} needs attention`}
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

      {projectCreateOpen ? (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(22,19,16,0.18)] px-4"
          onClick={() => setProjectCreateOpen(false)}
        >
          <form
            className="w-full max-w-[420px] rounded-[18px] border border-app-border bg-app-panel px-6 py-6 shadow-[0_24px_80px_rgba(34,24,16,0.18)]"
            onClick={(event) => event.stopPropagation()}
            onSubmit={async (event) => {
              event.preventDefault();
              const nextName = projectName.trim();
              if (!nextName) {
                return;
              }
              const created = await onCreateProject(nextName);
              if (created) {
                setProjectCreateOpen(false);
                setProjectName("");
              }
            }}
          >
            <div className="text-[24px] font-semibold text-app-text">新建项目</div>
            <input
              autoFocus
              className="mt-5 w-full rounded-[10px] border border-app-border bg-app-panel-strong px-3 py-2.5 text-[15px] text-app-text outline-none transition focus:border-app-border-strong"
              onChange={(event) => setProjectName(event.target.value)}
              placeholder="项目名称"
              value={projectName}
            />
            <div className="mt-6 flex justify-end gap-2">
              <button
                className="rounded-[8px] px-4 py-2 text-[14px] font-medium text-app-muted transition hover:bg-app-panel-soft hover:text-app-text"
                onClick={() => setProjectCreateOpen(false)}
                type="button"
              >
                取消
              </button>
              <button
                className="inline-flex items-center gap-2 rounded-[8px] bg-app-accent-soft px-4 py-2 text-[14px] font-semibold text-app-accent-strong transition hover:bg-app-panel-soft disabled:opacity-60"
                disabled={projectIsSaving || !projectName.trim()}
                type="submit"
              >
                {projectIsSaving ? <LoaderCircle className="size-4 animate-spin" /> : <Plus className="size-4" />}
                <span>创建</span>
              </button>
            </div>
          </form>
        </div>
      ) : null}

      <SidebarDialog
        onCancel={() => setDialogState(null)}
        onConfirmDelete={async () => {
          if (!dialogState || dialogState.type !== "delete") {
            return;
          }

          if (dialogState.kind === "battle") {
            await onDeleteBattle(dialogState.id);
          } else if (dialogState.kind === "debate") {
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

          if (dialogState.kind === "battle") {
            await onRenameBattle(dialogState.id, nextTitle);
          } else if (dialogState.kind === "debate") {
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
