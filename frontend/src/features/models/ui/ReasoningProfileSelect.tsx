import { Check, ChevronDown } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { ModelOption, ReasoningProfileValue } from "../../../types";
import { cn, sidebarMenuPanelClass } from "../../workspace/ui/sidebar/styles";
import {
  normalizeReasoningProfileForModel,
  reasoningProfileLabelForModel,
  reasoningProfileOptionsForModel,
  supportsReasoningSelection,
} from "../lib/reasoningProfiles";

interface ReasoningProfileSelectProps {
  modelOption: ModelOption;
  value: ReasoningProfileValue;
  onChange: (value: ReasoningProfileValue) => void;
  compact?: boolean;
  fullWidth?: boolean;
  label?: string;
  menuPlacement?: "top" | "bottom";
  triggerStyle?: "default" | "ghost";
  triggerContent?: "label_value" | "label_only";
}

export function ReasoningProfileSelect({
  modelOption,
  value,
  onChange,
  compact = false,
  fullWidth = false,
  label = "Reasoning",
  menuPlacement = "top",
  triggerStyle = "default",
  triggerContent = "label_value",
}: ReasoningProfileSelectProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const visible = supportsReasoningSelection(modelOption);
  const currentValue = normalizeReasoningProfileForModel(modelOption, value);
  const options = useMemo(() => reasoningProfileOptionsForModel(modelOption), [modelOption]);
  const displayLabel = reasoningProfileLabelForModel(modelOption, currentValue);

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

  if (!visible || options.length === 0) {
    return null;
  }

  const isGhost = triggerStyle === "ghost";
  const buttonClassName = compact
    ? isGhost
      ? `inline-flex h-10 min-w-0 items-center bg-transparent px-0 py-0 text-left text-[14px] font-medium tracking-[-0.02em] text-[#5f564a] transition hover:text-app-text ${fullWidth ? "w-full justify-between" : ""}`
      : `inline-flex h-10 min-w-0 items-center rounded-[8px] border border-app-border bg-white/92 px-3 text-left text-[14px] font-medium tracking-[-0.02em] text-[#5f564a] transition hover:bg-[#f8f3eb] ${fullWidth ? "w-full justify-between" : ""}`
    : `inline-flex h-10 min-w-0 items-center rounded-[8px] border border-app-border bg-app-panel-strong px-3 text-left text-[14px] font-medium tracking-[-0.02em] text-[#5f564a] transition hover:bg-app-panel-soft ${fullWidth ? "w-full justify-between" : ""}`;
  const menuPositionClassName = compact
    ? menuPlacement === "bottom"
      ? "top-[calc(100%+10px)]"
      : "bottom-[calc(100%+10px)]"
    : menuPlacement === "bottom"
      ? "top-[calc(100%+8px)]"
      : "bottom-[calc(100%+8px)]";
  const menuClassName = compact
    ? `absolute ${menuPositionClassName} left-0 z-20 w-[min(180px,calc(100vw-5rem))] ${sidebarMenuPanelClass}`
    : `absolute ${menuPositionClassName} left-0 z-20 min-w-full ${sidebarMenuPanelClass} ${fullWidth ? "w-full" : "sm:w-max sm:max-w-[240px]"}`;
  const itemClassName = (active: boolean) =>
    compact
      ? cn(
          "flex h-10 w-full items-center justify-between gap-2 whitespace-nowrap px-3 text-left text-[14px] font-medium tracking-[-0.02em] transition-colors focus:outline-none focus-visible:outline-none",
          "bg-app-panel-strong text-[#5f564a] hover:bg-app-panel-soft",
        )
      : cn(
          "flex h-10 w-full items-center justify-between gap-2 whitespace-nowrap px-3 text-left text-[14px] font-medium tracking-[-0.02em] transition-colors focus:outline-none focus-visible:outline-none",
          active
            ? "bg-app-panel-soft text-[#5f564a]"
            : "bg-app-panel-strong text-[#5f564a] hover:bg-app-panel-soft",
        );

  return (
    <div className={`relative min-w-0 ${fullWidth ? "w-full" : "shrink-0"}`} ref={rootRef}>
      <button className={buttonClassName} onClick={() => setOpen((current) => !current)} type="button">
        {fullWidth ? (
          <span className="min-w-0 truncate text-[#5f564a]">{displayLabel}</span>
        ) : (
          <>
            {triggerContent === "label_only" ? (
              <span className="shrink-0 whitespace-nowrap text-[#5f564a]">{label}</span>
            ) : (
              <span className="flex min-w-0 items-center gap-1.5">
                <span className="shrink-0 whitespace-nowrap text-[#5f564a]">{label}:</span>
                <span className="min-w-0 truncate text-[#5f564a]">{displayLabel}</span>
              </span>
            )}
            <ChevronDown className={`ml-2 size-4 shrink-0 text-[#5f564a] transition ${open ? "rotate-180" : ""}`} />
          </>
        )}
        {fullWidth ? (
          <ChevronDown className={`size-4 shrink-0 text-[#5f564a] transition ${open ? "rotate-180" : ""}`} />
        ) : null}
      </button>

      {open ? (
        <div className={menuClassName}>
          {options.map((option) => {
            const active = option.value === currentValue;
            return (
              <button
                key={option.value}
                className={itemClassName(active)}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                type="button"
              >
                <span className="truncate">{option.label}</span>
                {active ? <Check className="size-4 text-[#5f564a]" /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
