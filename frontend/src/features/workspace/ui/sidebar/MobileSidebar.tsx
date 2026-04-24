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
        className={`fixed inset-y-0 left-0 z-30 w-screen transform transition-transform duration-300 ease-out md:hidden ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        onTouchEnd={handleTouchEnd}
        onTouchStart={handleTouchStart}
      >
        <div className="flex h-full flex-col border-r border-app-border bg-app-sidebar">
          <div className="shrink-0 border-b border-app-border/70 px-4 pt-4 pb-3">
            <button
              aria-label={open ? "Close sidebar" : "Open sidebar"}
              className="flex w-full items-center rounded-lg text-left text-app-text transition hover:text-app-text focus:outline-none focus-visible:ring-2 focus-visible:ring-app-border-strong"
              onClick={onToggleSidebar}
              type="button"
            >
              <SidebarBrand title={contentProps.viewerName || "Chatchat"} />
            </button>
          </div>
          <div className="min-h-0 flex-1">
            <SidebarContent {...contentProps} mode="mobile" />
          </div>
          <MobileSidebarFooter
            onLogout={contentProps.onLogout}
            onOpenSettings={contentProps.onOpenSettings}
          />
        </div>
      </div>
    </>
  );
}
