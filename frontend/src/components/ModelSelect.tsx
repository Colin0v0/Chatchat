import { Check, ChevronDown } from "lucide-react";
import { Fragment, useEffect, useRef, useState } from "react";

import { toModelLabel } from "../lib/models";
import type { ModelOption } from "../types";
import { cn, sidebarMenuItemClass, sidebarMenuPanelClass } from "./sidebar/styles";

interface ModelSelectProps {
  model: string;
  models: ModelOption[];
  onChange: (value: string) => void;
  compact?: boolean;
  fullWidth?: boolean;
  label?: string;
  menuPlacement?: "top" | "bottom";
}

function createFallbackOption(id: string): ModelOption {
  return {
    id,
    label: toModelLabel(id),
    supports_thinking: false,
    supports_thinking_trace: false,
    supports_attachment_upload: false,
    chat_model: null,
    reasoning_model: null,
  };
}

function providerOf(modelId: string): string {
  const separatorIndex = modelId.indexOf(":");
  if (separatorIndex < 0) {
    return "unknown";
  }

  return modelId.slice(0, separatorIndex);
}

export function ModelSelect({
  model,
  models,
  onChange,
  compact = false,
  fullWidth = false,
  label = "Model",
  menuPlacement = "top",
}: ModelSelectProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const currentModel =
    models.find((item) => item.id === model) ??
    (model ? createFallbackOption(model) : { ...createFallbackOption(""), id: "", label });
  const displayModel = currentModel;
  const visibleModels = models;

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const buttonClassName = compact
    ? `inline-flex h-11 min-w-0 items-center gap-1.5 rounded-[14px] border border-app-border bg-white/92 px-3 text-left text-[15px] font-medium tracking-[-0.02em] text-[#5f564a] transition hover:bg-[#f8f3eb] ${fullWidth ? "w-full justify-between" : ""}`
    : `inline-flex h-10 min-w-0 items-center gap-2 rounded-lg border border-app-border bg-app-panel-strong px-3 text-left text-[15px] font-medium tracking-[-0.02em] text-[#5f564a] transition hover:bg-app-panel-soft ${fullWidth ? "w-full justify-between" : "sm:max-w-[320px]"}`;
  const menuPositionClassName = compact
    ? menuPlacement === "bottom"
      ? "top-[calc(100%+10px)]"
      : "bottom-[calc(100%+10px)]"
    : menuPlacement === "bottom"
      ? "top-[calc(100%+8px)]"
      : "bottom-[calc(100%+8px)]";
  const menuClassName = compact
    ? `absolute ${menuPositionClassName} left-0 z-20 w-[min(220px,calc(100vw-5rem))] ${sidebarMenuPanelClass}`
    : `absolute ${menuPositionClassName} left-0 z-20 min-w-full ${sidebarMenuPanelClass} ${fullWidth ? "w-full" : "sm:w-max sm:max-w-[320px]"}`;
  const itemClassName = (active: boolean) =>
    compact
      ? cn(
          sidebarMenuItemClass,
          "w-full justify-between bg-app-panel-strong py-3 text-[15px] font-medium tracking-[-0.02em] text-[#5f564a] hover:bg-app-panel-soft",
        )
      : cn(
          sidebarMenuItemClass,
          "w-full justify-between py-3 text-[15px] font-medium tracking-[-0.02em]",
          active
            ? "bg-app-panel-soft text-[#5f564a]"
            : "bg-app-panel-strong text-[#5f564a] hover:bg-app-panel-soft",
        );

  return (
    <div className="relative min-w-0 shrink-0" ref={rootRef}>
      <button className={buttonClassName} onClick={() => setOpen((value) => !value)} type="button">
        {fullWidth ? (
          <span className="min-w-0 truncate text-[#5f564a]">{displayModel.label}</span>
        ) : (
          <span className="flex min-w-0 items-center gap-1.5 sm:gap-2">
            <span className={`shrink-0 whitespace-nowrap ${compact ? "text-[#5f564a]" : "text-[#5f564a] sm:hidden"}`}>
              {label}
            </span>
            {compact ? null : <span className="hidden shrink-0 whitespace-nowrap text-[#5f564a] sm:inline">{label}:</span>}
            {compact ? null : <span className="hidden min-w-0 truncate text-[#5f564a] sm:inline">{displayModel.label}</span>}
          </span>
        )}
        <ChevronDown className={`size-4 shrink-0 text-[#5f564a] transition ${open ? "rotate-180" : ""}`} />
      </button>

      {open ? (
        <div className={menuClassName}>
          {visibleModels.map((item, index) => {
            const active = item.id === displayModel.id;
            const previousProvider = index > 0 ? providerOf(visibleModels[index - 1].id) : null;
            const currentProvider = providerOf(item.id);
            const showProviderDivider = previousProvider !== null && previousProvider !== currentProvider;

            return (
              <Fragment key={item.id}>
                {showProviderDivider ? <div className="border-t border-app-border/80" role="separator" /> : null}
                <button
                  className={itemClassName(active)}
                  onClick={() => {
                    onChange(item.id);
                    setOpen(false);
                  }}
                  type="button"
                >
                  <span className="truncate">{item.label}</span>
                  {active ? <Check className="size-4 text-[#5f564a]" /> : null}
                </button>
              </Fragment>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
