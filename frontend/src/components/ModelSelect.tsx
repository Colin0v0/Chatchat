import { Check, ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { toModelLabel } from "../lib/models";
import type { ModelOption } from "../types";

interface ModelSelectProps {
  model: string;
  models: ModelOption[];
  onChange: (value: string) => void;
}

function createFallbackOption(id: string): ModelOption {
  return {
    id,
    label: toModelLabel(id),
    supports_thinking: false,
    supports_thinking_trace: false,
    chat_model: null,
    reasoning_model: null,
  };
}

export function ModelSelect({ model, models, onChange }: ModelSelectProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const currentModel = models.find((item) => item.id === model) ?? createFallbackOption(model);
  const displayModelId =
    currentModel.supports_thinking && currentModel.reasoning_model === currentModel.id
      ? currentModel.chat_model ?? currentModel.id
      : currentModel.id;
  const displayModel =
    models.find((item) => item.id === displayModelId) ?? createFallbackOption(displayModelId);
  const visibleModels = models.filter(
    (item) => !(item.supports_thinking && item.reasoning_model === item.id),
  );

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, []);

  return (
    <div className="relative min-w-0 shrink-0" ref={rootRef}>
      <button
        className="inline-flex h-10 min-w-0 items-center gap-2 rounded-lg border border-app-border bg-app-panel-strong px-3 text-left text-[15px] font-medium tracking-[-0.01em] text-app-text transition hover:bg-app-panel-soft sm:max-w-[320px]"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className="shrink-0 whitespace-nowrap text-app-muted sm:hidden">Model</span>
          <span className="hidden shrink-0 whitespace-nowrap text-app-muted sm:inline">Model:</span>
          <span className="hidden min-w-0 truncate text-app-muted sm:inline">{displayModel.label}</span>
        </span>
        <ChevronDown
          className={`size-4 shrink-0 text-app-muted transition ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open ? (
        <div className="absolute bottom-[calc(100%+8px)] left-0 z-20 min-w-full overflow-hidden rounded-lg border border-app-border bg-app-panel-strong shadow-[0_12px_30px_rgba(39,28,18,0.08)] sm:w-max sm:max-w-[320px]">
          {visibleModels.map((item) => {
            const active = item.id === displayModelId;
            return (
              <button
                className={`flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-[14px] transition ${
                  active
                    ? "bg-app-panel-soft text-app-accent-strong"
                    : "bg-app-panel-strong text-app-text hover:bg-app-panel-soft"
                }`}
                key={item.id}
                onClick={() => {
                  onChange(item.chat_model ?? item.id);
                  setOpen(false);
                }}
                type="button"
              >
                <span className="truncate">{item.label}</span>
                {active ? <Check className="size-4" /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
