import { ChevronDown, LogOut, MessageSquarePlus, PanelLeftOpen, Scale, Settings2, type LucideIcon } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { AppLogo } from "../../../../shared/ui/AppLogo";
import { SIDEBAR_MOTION, cn, sidebarIconButtonClass, sidebarMenuItemClass, sidebarMenuPanelClass } from "./styles";

interface SidebarActionProps {
  icon: ReactNode;
  label: string;
  isInput?: boolean;
  value?: string;
  alignToRail?: boolean;
  onChange?: (value: string) => void;
  onClick?: () => void;
}

export function SidebarTooltip({ label }: { label: string }) {
  return (
    <div className="pointer-events-none absolute left-[calc(100%+10px)] top-1/2 z-30 -translate-y-1/2 whitespace-nowrap rounded-lg border border-app-border bg-app-panel px-3 py-2 text-[13px] font-medium text-app-text opacity-0 shadow-[0_10px_24px_rgba(59,43,28,0.12)] transition duration-150 group-hover:opacity-100">
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
          "flex h-12 items-center overflow-hidden rounded-[8px] border border-app-border bg-app-panel-strong text-app-muted",
          "transition-colors focus-within:border-app-border-strong",
          alignToRail ? "pl-0 pr-4" : "gap-3 px-4",
        )}
      >
        <IconSlot alignToRail={alignToRail} icon={icon} />
        <input
          className={cn(
            "h-full min-w-0 flex-1 bg-transparent text-[15px] placeholder:text-app-muted",
            alignToRail ? "pl-0 pr-0" : "px-0",
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
        "flex h-12 items-center rounded-[8px]",
        "text-[15px] font-medium tracking-[-0.02em] text-app-text transition-colors",
        "hover:bg-app-panel-soft focus:outline-none focus-visible:outline-none focus-visible:ring-0",
        alignToRail ? "pl-0 pr-4" : "gap-3 px-4",
      )}
      onClick={onClick}
      type="button"
    >
      <IconSlot alignToRail={alignToRail} icon={icon} />
      <span>{label}</span>
    </button>
  );
}

export function SidebarBrand({
  compact = false,
  gapClassName = "gap-3",
  logoFrameClassName = "h-9 w-9",
  showSubtitle = true,
  titleClassName = "text-[15px] font-semibold tracking-[-0.02em]",
  title = "Chatchat",
}: {
  compact?: boolean;
  gapClassName?: string;
  logoFrameClassName?: string;
  showSubtitle?: boolean;
  titleClassName?: string;
  title?: string;
}) {
  return (
    <div className={`flex min-w-0 items-center ${gapClassName}`}>
      <div className={`flex shrink-0 items-center justify-center text-[#13227a] ${logoFrameClassName}`}>
        <AppLogo className="h-[22px] w-[22px]" />
      </div>
      {!compact ? (
        <div className="min-w-0">
          <div className={`truncate ${titleClassName}`}>{title}</div>
          {showSubtitle ? (
            <div className="truncate text-[13px] tracking-[0.08em] text-app-muted lowercase">
              personal workspace
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function DesktopPinnedAction({
  open,
  icon,
  label,
  onClick,
}: {
  open: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <div className="group relative h-[38.5px]">
      <button
        aria-label={label}
        className={cn(
          sidebarIconButtonClass,
          "absolute inset-y-0 left-0 z-20 h-[38.5px] w-10",
          SIDEBAR_MOTION,
          open ? "pointer-events-none opacity-0" : "opacity-100",
        )}
        onClick={onClick}
        type="button"
      >
        {icon}
      </button>

      <button
        aria-hidden={!open}
        className={cn(
          "absolute inset-y-0 left-0 w-full overflow-hidden rounded-[8px] text-left text-app-muted",
          "transition-[background-color,color,opacity]",
          SIDEBAR_MOTION,
          open ? "pointer-events-auto opacity-100 hover:bg-app-panel-soft hover:text-app-text" : "pointer-events-none opacity-0",
        )}
        onClick={onClick}
        tabIndex={open ? 0 : -1}
        type="button"
      >
        <span className="flex h-full items-center whitespace-nowrap pl-0 pr-4 text-[15px] tracking-[-0.02em]">
          <IconSlot alignToRail icon={icon} />
          <span>{label}</span>
        </span>
      </button>

      {!open ? <SidebarTooltip label={label} /> : null}
    </div>
  );
}

export function SidebarCreateMenu({
  compact = false,
  label = "New chat",
  menuPlacement = "bottom",
  onNewChat,
  onNewDebate,
}: {
  compact?: boolean;
  label?: string;
  menuPlacement?: "bottom" | "right";
  onNewChat: () => void;
  onNewDebate: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const menuClassName =
    menuPlacement === "right"
      ? cn("absolute left-[calc(100%+10px)] top-0 z-30 min-w-[120px] py-1", sidebarMenuPanelClass)
      : cn("absolute right-0 top-[calc(100%+8px)] z-30 w-[260px] py-1", sidebarMenuPanelClass);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  return (
    <div className="group relative h-12" ref={menuRef}>
      <button
        aria-expanded={menuOpen}
        aria-haspopup="menu"
        aria-label="Create session"
        className={cn(
          sidebarIconButtonClass,
          "absolute inset-y-0 left-0 z-20 h-12 w-9",
          SIDEBAR_MOTION,
          compact ? "pointer-events-none opacity-0" : "opacity-100",
        )}
        onClick={() => setMenuOpen((current) => !current)}
        tabIndex={compact ? -1 : 0}
        type="button"
      >
        <MessageSquarePlus className="size-4" />
      </button>

      <button
        aria-expanded={menuOpen}
        aria-haspopup="menu"
        aria-hidden={!compact}
        className={cn(
          "absolute inset-y-0 left-0 w-full overflow-hidden rounded-[8px] text-left text-app-muted",
          "transition-[background-color,color,opacity]",
          SIDEBAR_MOTION,
          compact
            ? cn(
                "pointer-events-auto opacity-100",
                menuOpen ? "bg-app-panel-soft text-app-text" : "hover:bg-app-panel-soft hover:text-app-text",
              )
            : "pointer-events-none opacity-0",
        )}
        onClick={() => setMenuOpen((current) => !current)}
        tabIndex={compact ? 0 : -1}
        type="button"
      >
        <span className="flex h-full items-center whitespace-nowrap pl-0 pr-4 text-[15px] tracking-[-0.02em]">
          <IconSlot alignToRail icon={<MessageSquarePlus className="size-4" />} />
          <span>{label}</span>
          <ChevronDown className={`ml-auto size-4 shrink-0 transition ${menuOpen ? "rotate-180" : ""}`} />
        </span>
      </button>

      {menuOpen ? (
        <div className={menuClassName}>
          <button
            className={`${sidebarMenuItemClass} min-h-12 w-full gap-0 px-0 py-0 text-app-text hover:text-app-accent-strong`}
            onClick={() => {
              setMenuOpen(false);
              onNewChat();
            }}
            type="button"
          >
            <span className="flex h-full w-full items-center whitespace-nowrap pl-0 pr-4 text-[15px] tracking-[-0.02em]">
              <IconSlot alignToRail icon={<MessageSquarePlus className="size-4" />} />
              <span>新建聊天</span>
              <span aria-hidden="true" className="ml-auto size-4 shrink-0" />
            </span>
          </button>
          <button
            className={`${sidebarMenuItemClass} min-h-12 w-full gap-0 px-0 py-0 text-app-text hover:text-app-accent-strong`}
            onClick={() => {
              setMenuOpen(false);
              onNewDebate();
            }}
            type="button"
          >
            <span className="flex h-full w-full items-center whitespace-nowrap pl-0 pr-4 text-[15px] tracking-[-0.02em]">
              <IconSlot alignToRail icon={<Scale className="size-4" />} />
              <span>发起辩论</span>
              <span aria-hidden="true" className="ml-auto size-4 shrink-0" />
            </span>
          </button>
        </div>
      ) : null}

      {!compact && menuPlacement === "right" && !menuOpen ? <SidebarTooltip label={label} /> : null}
    </div>
  );
}

export function DesktopPinnedHeader({
  open,
  title,
}: {
  open: boolean;
  title: string;
}) {
  return (
    <div className="shrink-0 border-b border-app-border/70 px-[10px] pt-4 pb-3">
      <div className="relative h-9">
        <div className="absolute inset-y-0 left-0 flex items-center">
          <SidebarBrand compact title={title} />
        </div>

        <div
          aria-hidden={!open}
          className={cn(
            "min-w-0 overflow-hidden whitespace-nowrap",
            open ? "max-w-[220px] pl-12 opacity-100" : "pointer-events-none max-w-0 pl-0 opacity-0",
          )}
        >
          <div className="truncate text-[15px] font-semibold tracking-[-0.02em]">{title}</div>
          <div className="truncate text-[13px] tracking-[0.08em] text-app-muted lowercase">
            personal workspace
          </div>
        </div>
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

function SidebarFooterAction({
  active = false,
  icon,
  label,
  onClick,
  className,
}: {
  active?: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
  className?: string;
}) {
  return (
    <button
      aria-label={label}
      className={cn(sidebarIconButtonClass, "h-9 w-9", active && "bg-app-panel-soft text-app-text", className)}
      onClick={onClick}
      type="button"
    >
      {icon}
    </button>
  );
}

export function DesktopSidebarFooter({
  settingsActive = false,
  open,
  onLogout,
  onOpenSettings,
  onToggle,
}: {
  settingsActive?: boolean;
  open: boolean;
  onLogout?: () => void;
  onOpenSettings?: () => void;
  onToggle: () => void;
}) {
  return (
    <div className="shrink-0 border-t border-app-border/70 px-[10px] pb-4 pt-3">
      <div
        className={cn(
          "flex",
          open ? "h-9 items-center justify-between gap-2" : "flex-col items-start gap-1",
        )}
      >
        <button
          aria-label={open ? "Collapse sidebar" : "Expand sidebar"}
          className={cn(
            sidebarIconButtonClass,
            "text-app-text hover:text-app-text",
            "h-9 w-9 shrink-0",
            SIDEBAR_MOTION,
          )}
          onClick={onToggle}
          type="button"
        >
          <PanelLeftOpen className="size-4" />
        </button>

        {open && (onOpenSettings || onLogout) ? (
          <div className="flex items-center gap-1">
            {onOpenSettings ? (
              <SidebarFooterAction
                active={settingsActive}
                icon={<Settings2 className="size-4" />}
                label="设置"
                onClick={onOpenSettings}
              />
            ) : null}

            {onLogout ? (
              <SidebarFooterAction
                icon={<LogOut className="size-4" />}
                label="退出登录"
                onClick={onLogout}
              />
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function MobileSidebarFooter({
  settingsActive = false,
  onLogout,
  onOpenSettings,
}: {
  settingsActive?: boolean;
  onLogout?: () => void;
  onOpenSettings?: () => void;
}) {
  if (!onLogout && !onOpenSettings) {
    return null;
  }

  return (
    <div className="shrink-0 border-t border-app-border/70 px-4 pt-3 pb-4">
      <div className="flex min-h-9 items-center justify-start gap-1">
        {onOpenSettings ? (
          <SidebarFooterAction
            active={settingsActive}
            icon={<Settings2 className="size-4" />}
            label="设置"
            onClick={onOpenSettings}
          />
        ) : null}
        {onLogout ? (
          <SidebarFooterAction
            icon={<LogOut className="size-4" />}
            label="退出登录"
            onClick={onLogout}
          />
        ) : null}
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
