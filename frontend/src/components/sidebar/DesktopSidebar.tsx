import { DesktopPinnedHeader, DesktopSidebarToggle } from "./SidebarActions";
import { SidebarContent } from "./SidebarContent";
import { SIDEBAR_MOTION, cn } from "./styles";
import type { SidebarProps } from "./types";

export function DesktopSidebar({ open, onToggleSidebar, ...contentProps }: SidebarProps) {
  return (
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
        open={open}
      />
      <div
        aria-hidden={!open}
        className={cn(
          "h-full overflow-hidden transition-opacity",
          SIDEBAR_MOTION,
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      >
        <SidebarContent {...contentProps} mode="desktop" />
      </div>
      <DesktopSidebarToggle onToggle={onToggleSidebar} open={open} />
    </div>
  );
}
