import { ArrowUp, BookOpen, Sparkles, Square } from "lucide-react";
import { type KeyboardEvent, type ReactNode } from "react";

import { ModelSelect } from "./ModelSelect";
import type { ModelOption } from "../types";

interface ChatComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  isStreaming: boolean;
  model: string;
  models: ModelOption[];
  onModelChange: (value: string) => void;
  ragEnabled: boolean;
  thinkingEnabled: boolean;
  thinkingAvailable: boolean;
  onToggleRag: () => void;
  onToggleThinking: () => void;
  centered?: boolean;
}

function ToggleChip({
  active,
  disabled = false,
  icon,
  label,
  onClick,
}: {
  active: boolean;
  disabled?: boolean;
  icon?: ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-pressed={active}
      className={`inline-flex h-10 shrink-0 items-center gap-2 rounded-lg border px-3 text-[14px] font-medium tracking-[-0.01em] transition-colors ${
        disabled
          ? "cursor-not-allowed border-app-border bg-app-panel-strong text-app-muted/45"
          : active
            ? "border-app-border-strong bg-app-panel-soft text-app-text"
            : "border-app-border bg-app-panel-strong text-app-muted hover:bg-app-panel-soft"
      }`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {icon ? <span className="flex h-4 w-4 items-center justify-center">{icon}</span> : null}
      <span>{label}</span>
    </button>
  );
}

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  onStop,
  isStreaming,
  model,
  models,
  onModelChange,
  ragEnabled,
  thinkingEnabled,
  thinkingAvailable,
  onToggleRag,
  onToggleThinking,
  centered = false,
}: ChatComposerProps) {
  const canSubmit = value.trim().length > 0;

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (isStreaming || canSubmit) {
        isStreaming ? onStop() : onSubmit();
      }
    }
  };

  return (
    <div className={`w-full ${centered ? "max-w-[880px]" : "mx-auto max-w-[920px]"}`}>
      <div className="rounded-lg border border-app-border bg-app-panel-strong shadow-[0_1px_3px_rgba(39,28,18,0.05)]">
        <textarea
          className="min-h-24 w-full resize-none bg-transparent px-4 py-4 text-[16px] leading-7 text-app-text placeholder:text-[#9a9387]"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything"
          rows={centered ? 3 : 2}
          value={value}
        />

        <div className="flex items-center gap-3 px-4 py-3">
          <div className="flex min-w-0 flex-1 items-center gap-2 overflow-visible">
            <ToggleChip active={ragEnabled} icon={<BookOpen className="size-4" />} label="RAG" onClick={onToggleRag} />
            <ToggleChip
              active={thinkingEnabled}
              disabled={!thinkingAvailable}
              icon={<Sparkles className="size-4" />}
              label="Thinking"
              onClick={onToggleThinking}
            />
            <ModelSelect model={model} models={models} onChange={onModelChange} />
          </div>

          <button
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors ${
              isStreaming
                ? "bg-app-danger text-white hover:bg-app-danger"
                : canSubmit
                  ? "bg-app-accent-soft text-app-accent-strong hover:bg-[#e7ddcf]"
                  : "bg-app-panel-soft text-app-muted/55"
            }`}
            disabled={!isStreaming && !canSubmit}
            onClick={isStreaming ? onStop : onSubmit}
            type="button"
          >
            {isStreaming ? <Square className="size-3.5 fill-current" /> : <ArrowUp className="size-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}
