import { SidebarContent } from "./SidebarContent";
import type { SidebarProps } from "./types";

export function MobileSidebar({ open, isDesktop, onToggleSidebar, ...contentProps }: SidebarProps) {
  return (
    <>
      <div
        className={`fixed inset-y-0 right-0 z-20 w-[280px] transform transition-transform duration-300 ease-out md:hidden ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <div className="h-full border-l border-app-border bg-app-sidebar shadow-[0_0_0_1px_rgba(0,0,0,0.03)]">
          <SidebarContent {...contentProps} mode="mobile" />
        </div>
      </div>

      {!isDesktop ? (
        <div
          aria-hidden={open ? undefined : true}
          className={`fixed inset-0 z-10 bg-black/10 transition-opacity duration-300 md:hidden ${
            open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
          }`}
          onClick={onToggleSidebar}
        />
      ) : null}
    </>
  );
}