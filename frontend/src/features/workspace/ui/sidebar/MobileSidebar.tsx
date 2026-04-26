import { ArrowLeft } from "lucide-react";
import { useRef } from "react";

import { MobileSidebarFooter, SidebarBrand } from "./SidebarActions";
import { SidebarContent } from "./SidebarContent";
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
        className={`fixed inset-0 z-30 md:hidden ${open ? "pointer-events-auto" : "pointer-events-none hidden"}`}
      >
        <button
          aria-label="关闭侧边栏"
          className="absolute inset-0 bg-black/10"
          onClick={onToggleSidebar}
          type="button"
        />
        <div
          className={`relative flex h-full min-w-[280px] max-w-[calc(100vw-56px)] w-[min(72vw,340px)] transform flex-col border-r border-app-border bg-app-sidebar shadow-[18px_0_48px_rgba(34,24,16,0.12)] ${
            open ? "translate-x-0" : "-translate-x-full"
          }`}
          onTouchEnd={handleTouchEnd}
          onTouchStart={handleTouchStart}
        >
          <div className="shrink-0 border-b border-app-border/70 px-3 pt-4 pb-3">
            <div className="flex items-center justify-between gap-3">
              <SidebarBrand logoFrameClassName="h-8 w-8" title={contentProps.viewerName || "Chatchat"} />
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
