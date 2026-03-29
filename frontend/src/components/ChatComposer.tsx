import { ArrowUp, BookOpen, Globe, Plus, Sparkles, Square } from "lucide-react";
import { useRef, type ChangeEvent, type KeyboardEvent, type ReactNode } from "react";

import type { ComposerImageDraft } from "../app/useComposerImages";
import type { ModelOption } from "../types";
import { ComposerImageStrip } from "./composer/ComposerImageStrip";
import { ComposerMobileToolbar } from "./composer/ComposerMobileToolbar";
import { ModelSelect } from "./ModelSelect";

interface ChatComposerProps {
  value: string;
  images: ComposerImageDraft[];
  onChange: (value: string) => void;
  onSelectImages: (files: FileList | File[]) => void;
  onRemoveImage: (imageId: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  isStreaming: boolean;
  model: string;
  models: ModelOption[];
  onModelChange: (value: string) => void;
  ragEnabled: boolean;
  webEnabled: boolean;
  thinkingEnabled: boolean;
  thinkingAvailable: boolean;
  imageUploadAvailable: boolean;
  onToggleRag: () => void;
  onToggleWeb: () => void;
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
  images,
  onChange,
  onSelectImages,
  onRemoveImage,
  onSubmit,
  onStop,
  isStreaming,
  model,
  models,
  onModelChange,
  ragEnabled,
  webEnabled,
  thinkingEnabled,
  thinkingAvailable,
  imageUploadAvailable,
  onToggleRag,
  onToggleWeb,
  onToggleThinking,
  centered = false,
}: ChatComposerProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const hasDraft = value.trim().length > 0 || images.length > 0;

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (isStreaming || hasDraft) {
        isStreaming ? onStop() : onSubmit();
      }
    }
  };

  const handleSelectImages = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      onSelectImages(event.target.files);
    }
    event.target.value = "";
  };

  return (
    <div className={`w-full ${centered ? "max-w-[880px]" : "mx-auto max-w-[920px]"}`}>
      <div className="rounded-lg border border-app-border bg-app-panel-strong shadow-[0_1px_3px_rgba(39,28,18,0.05)]">
        <input
          accept="image/png,image/jpeg,image/webp,image/gif"
          className="hidden"
          multiple
          onChange={handleSelectImages}
          ref={inputRef}
          type="file"
        />

        <ComposerImageStrip images={images} onRemove={onRemoveImage} />

        <textarea
          className="min-h-24 w-full resize-none bg-transparent px-4 py-4 text-[16px] leading-7 text-app-text placeholder:text-[#9a9387]"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything or add an image"
          rows={centered ? 3 : 2}
          value={value}
        />

        <div className="hidden items-center gap-3 px-4 py-3 md:flex">
          <div className="flex min-w-0 flex-1 items-center gap-2 overflow-visible">
            <button
              aria-label="Add image"
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border transition-colors ${
                imageUploadAvailable
                  ? "border-app-border bg-app-panel-strong text-app-muted hover:bg-app-panel-soft hover:text-app-text"
                  : "cursor-not-allowed border-app-border bg-app-panel-strong text-app-muted/45"
              }`}
              disabled={isStreaming || !imageUploadAvailable}
              onClick={() => inputRef.current?.click()}
              type="button"
            >
              <Plus className="size-4" />
            </button>
            <ToggleChip active={ragEnabled} icon={<BookOpen className="size-4" />} label="RAG" onClick={onToggleRag} />
            <ToggleChip active={webEnabled} icon={<Globe className="size-4" />} label="Web" onClick={onToggleWeb} />
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
                : hasDraft
                  ? "bg-app-accent-soft text-app-accent-strong hover:bg-[#e7ddcf]"
                  : "bg-app-panel-soft text-app-muted/55"
            }`}
            disabled={!isStreaming && !hasDraft}
            onClick={isStreaming ? onStop : onSubmit}
            type="button"
          >
            {isStreaming ? <Square className="size-3.5 fill-current" /> : <ArrowUp className="size-4" />}
          </button>
        </div>

        <div className="px-4 pb-3 pt-1 md:hidden">
          <div className="flex items-end gap-3">
            <div className="min-w-0 flex-1">
              <ComposerMobileToolbar
                imageUploadAvailable={imageUploadAvailable}
                imagesPresent={images.length > 0}
                isStreaming={isStreaming}
                model={model}
                models={models}
                onAddImage={() => inputRef.current?.click()}
                onModelChange={onModelChange}
                onToggleRag={onToggleRag}
                onToggleThinking={onToggleThinking}
                onToggleWeb={onToggleWeb}
                ragEnabled={ragEnabled}
                thinkingAvailable={thinkingAvailable}
                thinkingEnabled={thinkingEnabled}
                webEnabled={webEnabled}
              />
            </div>

            <button
              className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full transition-colors ${
                isStreaming
                  ? "bg-app-danger text-white hover:bg-app-danger"
                  : hasDraft
                    ? "bg-[#18120d] text-white"
                    : "bg-[#ebe5db] text-[#9c9285]"
              }`}
              disabled={!isStreaming && !hasDraft}
              onClick={isStreaming ? onStop : onSubmit}
              type="button"
            >
              {isStreaming ? <Square className="size-3.5 fill-current" /> : <ArrowUp className="size-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
