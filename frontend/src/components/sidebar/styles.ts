export const SIDEBAR_MOTION = "duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)]";

export function cn(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export const sidebarIconButtonClass = cn(
  "flex items-center justify-center rounded-[8px] text-app-muted outline-none transition-colors",
  "hover:text-app-text focus:outline-none focus-visible:outline-none focus-visible:ring-0",
);

export const sidebarMenuPanelClass =
  "overflow-hidden rounded-[8px] border border-app-border bg-app-panel-strong shadow-[0_16px_40px_rgba(34,24,16,0.12)]";

export const sidebarMenuItemClass = cn(
  "flex items-center gap-2 whitespace-nowrap px-4 py-2 text-left text-[14px] transition-colors",
  "focus:outline-none focus-visible:outline-none",
);