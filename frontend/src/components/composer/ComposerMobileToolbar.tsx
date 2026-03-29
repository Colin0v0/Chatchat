import { BookOpen, Globe, Plus, Sparkles } from "lucide-react";
import type { ReactNode } from "react";

import { ModelSelect } from "../ModelSelect";
import type { ModelOption } from "../../types";

interface ComposerMobileToolbarProps {
  imageUploadAvailable: boolean;
  imagesPresent: boolean;
  isStreaming: boolean;
  model: string;
  models: ModelOption[];
  onAddImage: () => void;
  onModelChange: (value: string) => void;
  ragEnabled: boolean;
  webEnabled: boolean;
  thinkingAvailable: boolean;
  thinkingEnabled: boolean;
  onToggleRag: () => void;
  onToggleWeb: () => void;
  onToggleThinking: () => void;
}

interface MobileToolChipProps {
  active: boolean;
  disabled?: boolean;
  icon: ReactNode;
  label: string;
  onClick: () => void;
}

function MobileToolChip({ active, disabled = false, icon, label, onClick }: MobileToolChipProps) {
  return (
    <button
      aria-pressed={active}
      className={`inline-flex h-11 shrink-0 items-center gap-2 rounded-[14px] border px-3.5 text-[15px] font-medium tracking-[-0.02em] transition-colors ${
        disabled
          ? "cursor-not-allowed border-app-border bg-[#f7f2ea] text-app-muted/45"
          : active
            ? "border-[#d8c1a3] bg-[#efe3d3] text-[#5b4128]"
            : "border-app-border bg-white/88 text-[#5f564a] hover:bg-[#f8f3eb]"
      }`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      <span className="flex size-4 items-center justify-center">{icon}</span>
      <span className="whitespace-nowrap">{label}</span>
    </button>
  );
}

export function ComposerMobileToolbar({
  imageUploadAvailable,
  imagesPresent,
  isStreaming,
  model,
  models,
  onAddImage,
  onModelChange,
  ragEnabled,
  webEnabled,
  thinkingAvailable,
  thinkingEnabled,
  onToggleRag,
  onToggleWeb,
  onToggleThinking,
}: ComposerMobileToolbarProps) {
  const addDisabled = isStreaming || (!imageUploadAvailable && imagesPresent);

  return (
    <div className="md:hidden">
      <div className="flex items-center gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <button
          aria-label="Add image"
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] border transition-colors ${
            addDisabled
              ? "cursor-not-allowed border-app-border bg-[#f7f2ea] text-app-muted/45"
              : "border-app-border bg-white/92 text-[#5f564a] hover:bg-[#f8f3eb] hover:text-app-text"
          }`}
          disabled={addDisabled}
          onClick={onAddImage}
          type="button"
        >
          <Plus className="size-4.5" />
        </button>

        <MobileToolChip
          active={ragEnabled}
          icon={<BookOpen className="size-4" />}
          label="RAG"
          onClick={onToggleRag}
        />
        <MobileToolChip
          active={webEnabled}
          icon={<Globe className="size-4" />}
          label="Web"
          onClick={onToggleWeb}
        />
        <MobileToolChip
          active={thinkingEnabled}
          disabled={!thinkingAvailable}
          icon={<Sparkles className="size-4" />}
          label="Thinking"
          onClick={onToggleThinking}
        />

        <ModelSelect compact model={model} models={models} onChange={onModelChange} />
      </div>
    </div>
  );
}
