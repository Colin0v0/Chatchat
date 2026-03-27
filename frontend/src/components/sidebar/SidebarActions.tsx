import { MessageSquarePlus, PanelLeftOpen, Search, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { SIDEBAR_MOTION, cn, sidebarIconButtonClass } from "./styles";

interface SidebarActionProps {
  icon: ReactNode;
  label: string;
  isInput?: boolean;
  value?: string;
  alignToRail?: boolean;
  onChange?: (value: string) => void;
  onClick?: () => void;
}

function SidebarTooltip({ label }: { label: string }) {
  return (
    <div className="pointer-events-none absolute left-[calc(100%+10px)] top-1/2 z-30 -translate-y-1/2 whitespace-nowrap rounded-lg bg-app-accent px-3 py-2 text-[13px] font-medium text-white opacity-0 shadow-[0_10px_24px_rgba(59,43,28,0.18)] transition duration-150 group-hover:opacity-100">
      <span>{label}</span>
    </div>
  );
}

function IconSlot({ alignToRail, icon }: { alignToRail: boolean; icon: ReactNode }) {
  return (
    <span
      className={cn(
        alignToRail ? "flex h-full w-9 shrink-0 items-center justify-center" : "shrink-0",
        "text-app-muted",
      )}
    >
      {icon}
    </span>
  );
}

export function SidebarAction({
  icon,
  label,
  isInput = false,
  value = "",
  alignToRail = false,
  onChange,
  onClick,
}: SidebarActionProps) {
  if (isInput) {
    return (
      <label
        className={cn(
          "flex h-12 items-center rounded-[8px] border border-app-border bg-app-panel-strong text-app-muted",
          "transition-colors focus-within:border-app-border-strong",
          alignToRail ? "pl-0 pr-4" : "gap-3 px-4",
        )}
      >
        <IconSlot alignToRail={alignToRail} icon={icon} />
        <input
          className={cn(
            "w-full bg-transparent text-[15px] placeholder:text-app-muted",
            alignToRail && "min-w-0 pl-3",
          )}
          onChange={(event) => onChange?.(event.target.value)}
          placeholder={label}
          value={value}
        />
      </label>
    );
  }

  return (
    <button
      className={cn(
        "flex h-12 items-center gap-3 rounded-[8px] border border-app-border bg-app-panel-strong px-4",
        "text-[15px] font-medium tracking-[-0.02em] text-app-text transition-colors",
        "hover:bg-app-panel-soft focus:outline-none focus-visible:outline-none focus-visible:ring-0",
      )}
      onClick={onClick}
      type="button"
    >
      <IconSlot alignToRail={false} icon={icon} />
      <span>{label}</span>
    </button>
  );
}

export function SidebarBrand({
  compact = false,
  onIconClick,
}: {
  compact?: boolean;
  onIconClick?: () => void;
}) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <button
        aria-label="Open settings"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] bg-app-accent-soft text-[18px] font-semibold text-app-accent-strong"
        onClick={onIconClick}
        type="button"
      >
        C
      </button>
      {!compact ? (
        <div className="min-w-0">
          <div className="truncate text-[15px] font-semibold tracking-[-0.02em]">Chatchat</div>
          <div className="truncate text-[13px] tracking-[0.08em] text-app-muted lowercase">
            reasoning workspace
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function DesktopPinnedNewChatButton({ open, onClick }: { open: boolean; onClick: () => void }) {
  return (
    <div className="group relative h-12">
      <button
        aria-label="New chat"
        className={cn(sidebarIconButtonClass, "absolute inset-y-0 left-0 z-20 h-12 w-9")}
        onClick={onClick}
        type="button"
      >
        <MessageSquarePlus className="size-4" />
      </button>

      <button
        aria-hidden={!open}
        className={cn(
          "absolute inset-y-0 left-0 w-full overflow-hidden rounded-[8px] border border-app-border bg-app-panel-strong text-left text-app-muted",
          "transition-[background-color,color,opacity]",
          SIDEBAR_MOTION,
          open ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onClick}
        tabIndex={open ? 0 : -1}
        type="button"
      >
        <span className="flex h-full items-center whitespace-nowrap pl-12 pr-4 text-[15px] tracking-[-0.02em]">
          New chat
        </span>
      </button>

      {!open ? <SidebarTooltip label="New chat" /> : null}
    </div>
  );
}

export function DesktopPinnedHeader({
  open,
  onNewChat,
  onOpenSettings,
}: {
  open: boolean;
  onNewChat: () => void;
  onOpenSettings: () => void;
}) {
  return (
    <div className="absolute top-4 right-2 left-[10px] z-10">
      <div className="relative h-9">
        <div className="absolute inset-y-0 left-0">
          <SidebarBrand compact onIconClick={onOpenSettings} />
        </div>

        <div
          aria-hidden={!open}
          className={cn(
            "min-w-0 pl-12 transition-opacity",
            SIDEBAR_MOTION,
            open ? "opacity-100" : "pointer-events-none opacity-0",
          )}
        >
          <div className="truncate text-[15px] font-semibold tracking-[-0.02em]">Chatchat</div>
          <div className="truncate text-[13px] tracking-[0.08em] text-app-muted lowercase">
            reasoning workspace
          </div>
        </div>
      </div>

      <div className="mt-4">
        <DesktopPinnedNewChatButton onClick={onNewChat} open={open} />
      </div>
    </div>
  );
}

export function SidebarLoadingState() {
  return (
    <div className="flex min-h-full w-full items-start justify-center pt-[25%]">
      <div className="inline-flex items-center gap-2.5 px-3 py-2 text-[14px] text-app-muted/85">
        <span className="animate-[thinking-dot_1.8s_ease-in-out_infinite] tracking-[0.02em]">Loading</span>
        <span aria-hidden="true" className="inline-flex items-center gap-1.5 self-center">
          <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.15s_infinite]" />
          <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.3s_infinite]" />
          <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.45s_infinite]" />
        </span>
      </div>
    </div>
  );
}

export function DesktopSidebarToggle({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button
      aria-label={open ? "Collapse sidebar" : "Expand sidebar"}
      className={cn(sidebarIconButtonClass, "absolute bottom-4 left-[10px] z-20 h-9 w-9", SIDEBAR_MOTION)}
      onClick={onToggle}
      type="button"
    >
      <PanelLeftOpen className={cn("size-4 transition-transform", SIDEBAR_MOTION, open && "rotate-180")} />
    </button>
  );
}

export function SidebarIcon({ icon: Icon }: { icon: LucideIcon }) {
  return <Icon className="size-4" />;
}

export { Search };
