import { BookOpen, Check, Globe, Paperclip, Plus, Sparkles } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { ModelSelect } from "../ModelSelect";
import type { ModelOption, RetrievalMode } from "../../types";

interface ComposerMobileToolbarProps {
  attachmentUploadAvailable: boolean;
  attachmentsPresent: boolean;
  isStreaming: boolean;
  model: string;
  models: ModelOption[];
  onAddAttachment: () => void;
  onModelChange: (value: string) => void;
  retrievalMode: RetrievalMode;
  thinkingAvailable: boolean;
  thinkingEnabled: boolean;
  onToggleRag: () => void;
  onToggleWeb: () => void;
  onToggleThinking: () => void;
}

interface MobileMenuActionProps {
  active?: boolean;
  disabled?: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}

function MobileMenuAction({
  active = false,
  disabled = false,
  icon,
  label,
  onClick,
}: MobileMenuActionProps) {
  return (
    <button
      aria-pressed={active}
      className={`flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-[15px] font-medium tracking-[-0.02em] transition-colors ${
        disabled
          ? "cursor-not-allowed bg-app-panel-strong text-app-muted/45"
          : "bg-app-panel-strong text-[#5f564a] hover:bg-app-panel-soft"
      }`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <span className="flex items-center gap-3">
        <span className="flex size-4 items-center justify-center">{icon}</span>
        <span className="whitespace-nowrap">{label}</span>
      </span>
      {active ? <Check className="size-4 shrink-0 text-[#5b4128]" /> : null}
    </button>
  );
}

export function ComposerMobileToolbar({
  attachmentUploadAvailable,
  attachmentsPresent,
  isStreaming,
  model,
  models,
  onAddAttachment,
  onModelChange,
  retrievalMode,
  thinkingAvailable,
  thinkingEnabled,
  onToggleRag,
  onToggleWeb,
  onToggleThinking,
}: ComposerMobileToolbarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const addDisabled = isStreaming || !attachmentUploadAvailable;
  const ragEnabled = retrievalMode === "rag";
  const webEnabled = retrievalMode === "web";

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, []);

  return (
    <div className="md:hidden">
      <div className="flex items-center gap-2">
        <div className="relative shrink-0" ref={menuRef}>
          <button
            aria-expanded={menuOpen}
            aria-haspopup="menu"
            aria-label="Open tools"
            className="flex h-11 w-11 items-center justify-center rounded-[14px] border border-app-border bg-white/92 text-[#5f564a] transition-colors hover:bg-[#f8f3eb] hover:text-app-text"
            onClick={() => setMenuOpen((value) => !value)}
            type="button"
          >
            <Plus className={`size-4.5 transition-transform ${menuOpen ? "rotate-45" : ""}`} />
          </button>

          {menuOpen ? (
            <div className="absolute bottom-[calc(100%+10px)] left-0 z-20 w-[min(220px,calc(100vw-5rem))] overflow-hidden rounded-[18px] border border-app-border bg-app-panel-strong shadow-[0_18px_40px_rgba(39,28,18,0.14)]">
              <MobileMenuAction
                disabled={addDisabled}
                icon={<Paperclip className="size-4" />}
                label="Add file"
                onClick={() => {
                  onAddAttachment();
                  setMenuOpen(false);
                }}
              />
              <MobileMenuAction
                active={ragEnabled}
                icon={<BookOpen className="size-4" />}
                label="RAG"
                onClick={() => {
                  onToggleRag();
                  setMenuOpen(false);
                }}
              />
              <MobileMenuAction
                active={webEnabled}
                icon={<Globe className="size-4" />}
                label="Search"
                onClick={() => {
                  onToggleWeb();
                  setMenuOpen(false);
                }}
              />
              <MobileMenuAction
                active={thinkingEnabled}
                disabled={!thinkingAvailable}
                icon={<Sparkles className="size-4" />}
                label="Thinking"
                onClick={() => {
                  onToggleThinking();
                  setMenuOpen(false);
                }}
              />
            </div>
          ) : null}
        </div>

        <ModelSelect compact model={model} models={models} onChange={onModelChange} />
      </div>
      {attachmentsPresent ? <div className="sr-only">Attachments ready</div> : null}
    </div>
  );
}
