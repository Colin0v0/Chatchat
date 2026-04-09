import { useCallback, useEffect, useState } from "react";

import { DesktopPinnedHeader, DesktopSidebarFooter } from "./SidebarActions";
import { SidebarContent } from "./SidebarContent";
import { SidebarSearchDialog } from "./SidebarSearchDialog";
import { SIDEBAR_MOTION, cn } from "./styles";
import type { SidebarProps } from "./types";

export function DesktopSidebar({ open, onToggleSidebar, ...contentProps }: SidebarProps) {
  const [searchOpen, setSearchOpen] = useState(false);
  const handleOpenSearch = useCallback(() => setSearchOpen(true), []);
  const handleCloseSearch = useCallback(() => setSearchOpen(false), []);

  useEffect(() => {
    if (open) {
      setSearchOpen(false);
    }
  }, [open]);

  return (
    <>
      <div
        className={cn(
          "relative hidden h-full overflow-visible border-r border-app-border bg-app-sidebar transition-[width] md:block",
          SIDEBAR_MOTION,
          open ? "w-[280px]" : "w-[56px]",
        )}
      >
        <DesktopPinnedHeader
          onNewChat={contentProps.onNewChat}
          onOpenSettings={contentProps.onOpenSettings}
          onQueryChange={contentProps.onQueryChange}
          onSearch={handleOpenSearch}
          open={open}
          query={contentProps.query}
          title={contentProps.viewerName || "Chatchat"}
        />
        <div
          aria-hidden={!open}
          className={cn(
            "h-full overflow-hidden transition-opacity",
            SIDEBAR_MOTION,
            open ? "opacity-100" : "pointer-events-none opacity-0",
          )}
        >
          <SidebarContent {...contentProps} mode="desktop" open={open} />
        </div>
        <DesktopSidebarFooter onLogout={contentProps.onLogout} onToggle={onToggleSidebar} open={open} />
      </div>

      <SidebarSearchDialog
        activity={contentProps.activity}
        items={contentProps.items}
        onClose={handleCloseSearch}
        onQueryChange={contentProps.onQueryChange}
        onSelect={contentProps.onSelect}
        open={searchOpen}
        query={contentProps.query}
      />
    </>
  );
}
