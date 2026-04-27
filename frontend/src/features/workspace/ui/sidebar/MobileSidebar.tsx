import { ArrowLeft } from "lucide-react";
import { useRef } from "react";

import { MobileSidebarFooter, SidebarBrand } from "./SidebarActions";
import { SidebarContent } from "./SidebarContent";
import { SIDEBAR_MOTION, cn } from "./styles";
import type { SidebarProps } from "./types";

export function MobileSidebar({ open, isDesktop, onToggleSidebar, ...contentProps }: SidebarProps) {
  const touchStartXRef = useRef<number | null>(null);
  const touchStartYRef = useRef<number | null>(null);

  function handleTouchStart(event: React.TouchEvent<HTMLDivElement>) {
    const touch = event.touches[0];
    touchStartXRef.current = touch.clientX;
    touchStartYRef.current = touch.clientY;
  }

  function handleTouchEnd(event: React.TouchEvent<HTMLDivElement>) {
    if (!open || touchStartXRef.current === null || touchStartYRef.current === null) {
      touchStartXRef.current = null;
      touchStartYRef.current = null;
      return;
    }

    const touch = event.changedTouches[0];
    const deltaX = touch.clientX - touchStartXRef.current;
    const deltaY = touch.clientY - touchStartYRef.current;

    touchStartXRef.current = null;
    touchStartYRef.current = null;

    if (Math.abs(deltaX) < 56 || Math.abs(deltaX) <= Math.abs(deltaY)) {
      return;
    }

    if (deltaX < 0) {
      onToggleSidebar();
    }
  }

  return (
    <>
      <div
        aria-hidden={!open}
        className={cn(
          "fixed inset-0 z-30 transition-opacity md:hidden",
          SIDEBAR_MOTION,
          open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
        )}
      >
        <button
          aria-label="关闭侧边栏"
          className={cn(
            "absolute inset-0 bg-black/10 transition-opacity",
            SIDEBAR_MOTION,
            open ? "opacity-100" : "opacity-0",
          )}
          onClick={onToggleSidebar}
          type="button"
        />
        <div
          className={cn(
            "relative flex h-full min-w-[280px] max-w-[calc(100vw-56px)] w-[min(72vw,340px)] transform-gpu flex-col border-r border-app-border bg-app-sidebar shadow-[18px_0_48px_rgba(34,24,16,0.12)] transition-transform will-change-transform",
            SIDEBAR_MOTION,
            open ? "translate-x-0" : "-translate-x-full",
          )}
          onTouchEnd={handleTouchEnd}
          onTouchStart={handleTouchStart}
        >
          <div className="flex h-[68px] shrink-0 box-content items-center border-b border-app-border/70 px-3">
            <div className="flex w-full items-center justify-between gap-3">
              <SidebarBrand
                title={contentProps.viewerName || "Chatchat"}
              />
              <button
                aria-label="返回"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] text-app-muted transition-colors hover:bg-app-panel-soft hover:text-app-text focus:outline-none focus-visible:ring-2 focus-visible:ring-app-border-strong"
                onClick={onToggleSidebar}
                type="button"
              >
                <ArrowLeft className="size-4" />
              </button>
            </div>
          </div>
          <div className="min-h-0 flex-1">
            <SidebarContent {...contentProps} mode="mobile" />
          </div>
          <MobileSidebarFooter
            onLogout={contentProps.onLogout}
            onOpenSettings={contentProps.onOpenSettings}
            settingsActive={contentProps.settingsActive}
          />
        </div>
      </div>
    </>
  );
}
