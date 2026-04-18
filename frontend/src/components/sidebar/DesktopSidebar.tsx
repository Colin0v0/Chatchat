import { DesktopPinnedHeader, DesktopSidebarFooter } from "./SidebarActions";
import { SidebarContent } from "./SidebarContent";
import { SIDEBAR_MOTION, cn } from "./styles";
import type { SidebarProps } from "./types";

export function DesktopSidebar({ open, onToggleSidebar, ...contentProps }: SidebarProps) {
  return (
    <>
      <div
        className={cn(
          "relative hidden h-full overflow-visible border-r border-app-border bg-app-sidebar transition-[width] md:block",
          SIDEBAR_MOTION,
          open ? "w-[280px]" : "w-[56px]",
        )}
      >
        <DesktopPinnedHeader open={open} title={contentProps.viewerName || "Chatchat"} />
        <div className="h-full">
          <SidebarContent {...contentProps} mode="desktop" open={open} />
        </div>
        <DesktopSidebarFooter onLogout={contentProps.onLogout} onToggle={onToggleSidebar} open={open} />
      </div>
    </>
  );
}
