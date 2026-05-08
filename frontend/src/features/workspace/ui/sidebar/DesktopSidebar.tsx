import { DesktopPinnedHeader, DesktopSidebarFooter } from "./SidebarActions";
import { SidebarContent } from "./SidebarContent";
import { SIDEBAR_MOTION, cn } from "./styles";
import type { SidebarProps } from "./types";

export function DesktopSidebar({ open, onToggleSidebar, ...contentProps }: SidebarProps) {
  return (
    <>
      <div
        data-pet-anchor="sidebarEdge"
        className={cn(
          "relative hidden h-full overflow-hidden border-r border-app-border bg-app-sidebar transition-[width] md:flex md:flex-col",
          SIDEBAR_MOTION,
          open ? "w-[280px]" : "w-[56px]",
        )}
      >
        <DesktopPinnedHeader open={open} title={contentProps.viewerName || "Chatchat"} />
        <div className="min-h-0 flex-1">
          <SidebarContent {...contentProps} mode="desktop" open={open} />
        </div>
        <DesktopSidebarFooter
          onLogout={contentProps.onLogout}
          onOpenSettings={contentProps.onOpenSettings}
          onToggle={onToggleSidebar}
          open={open}
          settingsActive={contentProps.settingsActive}
        />
      </div>
    </>
  );
}
