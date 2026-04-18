import { ArrowUp, BookOpen, Globe, LoaderCircle, Mic, Plus, Square } from "lucide-react";
import { useRef, useState, type ClipboardEvent, type ChangeEvent, type DragEvent, type KeyboardEvent, type ReactNode } from "react";

import { findModelOption } from "../app/modelOptions";
import type { ComposerAttachmentDraft } from "../app/useComposerAttachments";
import type { ModelOption, ReasoningProfileValue, ToolMode } from "../types";
import { ComposerAttachmentStrip } from "./composer/ComposerAttachmentStrip";
import { ComposerMobileToolbar } from "./composer/ComposerMobileToolbar";
import { ModelSelect } from "./ModelSelect";
import { ReasoningProfileSelect } from "./ReasoningProfileSelect";

const ATTACHMENT_ACCEPT = [
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
  ".pdf",
  ".txt",
  ".md",
  ".markdown",
  ".py",
  ".js",
  ".jsx",
  ".ts",
  ".tsx",
  ".json",
  ".html",
  ".htm",
  ".xml",
  ".yaml",
  ".yml",
  ".csv",
  ".xlsx",
  ".docx",
].join(",");

interface ChatComposerProps {
  value: string;
  attachments: ComposerAttachmentDraft[];
  onChange: (value: string) => void;
  onSelectAttachments: (files: FileList | File[]) => void;
  onRemoveAttachment: (attachmentId: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  isRecording: boolean;
  isStreaming: boolean;
  isTranscribing: boolean;
  model: string;
  models: ModelOption[];
  onModelChange: (value: string) => void;
  reasoningProfile: ReasoningProfileValue;
  onReasoningProfileChange: (value: ReasoningProfileValue) => void;
  toolMode: ToolMode;
  submitBlocked: boolean;
  submitBlockedReason: string | null;
  attachmentUploadAvailable: boolean;
  onToggleRag: () => void;
  onToggleWeb: () => void;
  onToggleRecording: () => void;
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
  const disabledClassName = active
    ? "cursor-default border-app-border-strong bg-app-panel-soft text-app-text opacity-85"
    : "cursor-not-allowed border-app-border bg-app-panel-strong text-app-muted/45";

  return (
    <button
      aria-pressed={active}
      className={`inline-flex h-10 shrink-0 items-center gap-2 rounded-lg border px-3 text-[14px] font-medium tracking-[-0.01em] transition-colors ${
        disabled
          ? disabledClassName
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

function ComposerVoiceButton({
  compact = false,
  disabled,
  isRecording,
  isTranscribing,
  onClick,
}: {
  compact?: boolean;
  disabled: boolean;
  isRecording: boolean;
  isTranscribing: boolean;
  onClick: () => void;
}) {
  const sizeClassName = compact ? "h-11 w-11 rounded-[14px]" : "h-9 w-9 rounded-lg";
  const iconClassName = compact ? "size-4.5" : "size-4";
  const stateClassName = isRecording
    ? "bg-app-danger text-white hover:bg-app-danger"
    : disabled
      ? "bg-transparent text-app-muted/45"
      : "bg-transparent text-app-muted hover:text-app-text";

  return (
    <button
      aria-label={isRecording ? "Stop voice input" : "Start voice input"}
      className={`flex shrink-0 items-center justify-center transition-colors ${sizeClassName} ${stateClassName}`}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {isTranscribing ? (
        <LoaderCircle className={`${iconClassName} animate-spin`} />
      ) : isRecording ? (
        <Square className={compact ? "size-4 fill-current" : "size-3.5 fill-current"} />
      ) : (
        <Mic className={iconClassName} />
      )}
    </button>
  );
}

export function ChatComposer({
  value,
  attachments,
  onChange,
  onSelectAttachments,
  onRemoveAttachment,
  onSubmit,
  onStop,
  isRecording,
  isStreaming,
  isTranscribing,
  model,
  models,
  onModelChange,
  reasoningProfile,
  onReasoningProfileChange,
  toolMode,
  submitBlocked,
  submitBlockedReason,
  attachmentUploadAvailable,
  onToggleRag,
  onToggleWeb,
  onToggleRecording,
  centered = false,
}: ChatComposerProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const hasDraft = value.trim().length > 0 || attachments.length > 0;
  const canSubmit = !submitBlocked && hasDraft;
  const ragEnabled = toolMode === "knowledge";
  const webEnabled = toolMode === "search";
  const voiceDisabled = isStreaming || isTranscribing;
  const selectedModelOption = findModelOption(models, model);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (isStreaming || canSubmit) {
        isStreaming ? onStop() : onSubmit();
      }
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    if (!attachmentUploadAvailable || isStreaming || !event.clipboardData) {
      return;
    }

    const { items } = event.clipboardData;
    const files: File[] = [];

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind === "file") {
        const file = item.getAsFile();
        if (file) {
          files.push(file);
        }
      }
    }

    if (files.length > 0) {
      onSelectAttachments(files);
    }
  };

  const handleSelectAttachments = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      onSelectAttachments(event.target.files);
    }
    event.target.value = "";
  };

  const handleDragEnter = (event: DragEvent<HTMLDivElement>) => {
    if (!attachmentUploadAvailable || isStreaming || event.dataTransfer.files.length === 0) {
      return;
    }
    event.preventDefault();
    setDragActive(true);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    if (!attachmentUploadAvailable || isStreaming || event.dataTransfer.files.length === 0) {
      return;
    }
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    setDragActive(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
      return;
    }
    setDragActive(false);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    if (!attachmentUploadAvailable || isStreaming || event.dataTransfer.files.length === 0) {
      return;
    }
    event.preventDefault();
    setDragActive(false);
    onSelectAttachments(event.dataTransfer.files);
  };

  return (
    <div className={`w-full ${centered ? "mx-auto max-w-[880px]" : ""}`}>
      <div
        className={`relative rounded-lg border bg-app-panel-strong shadow-[0_1px_3px_rgba(39,28,18,0.05)] transition-colors ${
          dragActive ? "border-app-accent-strong bg-app-panel-soft" : "border-app-border"
        }`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <input
          accept={ATTACHMENT_ACCEPT}
          className="hidden"
          multiple
          onChange={handleSelectAttachments}
          ref={inputRef}
          type="file"
        />

        <ComposerAttachmentStrip attachments={attachments} onRemove={onRemoveAttachment} />

        <textarea
          className="min-h-24 max-h-[220px] w-full resize-none overflow-y-auto bg-transparent px-4 py-4 text-[16px] leading-7 text-app-text placeholder:text-[#9a9387] [field-sizing:fixed]"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder="Ask anything"
          rows={centered ? 3 : 2}
          title={submitBlockedReason ?? undefined}
          value={value}
        />

        {dragActive ? (
          <div className="pointer-events-none absolute inset-0 rounded-lg border border-dashed border-app-accent-strong bg-[rgba(248,242,233,0.82)]" />
        ) : null}

        <div className="hidden items-center gap-3 px-4 py-3 md:flex">
          <div className="flex min-w-0 flex-1 items-center gap-2 overflow-visible">
            <button
              aria-label="Add file"
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border transition-colors ${
                attachmentUploadAvailable
                  ? "border-app-border bg-app-panel-strong text-app-muted hover:bg-app-panel-soft hover:text-app-text"
                  : "cursor-not-allowed border-app-border bg-app-panel-strong text-app-muted/45"
              }`}
              disabled={isStreaming || !attachmentUploadAvailable}
              onClick={() => inputRef.current?.click()}
              type="button"
            >
              <Plus className="size-4" />
            </button>
            <ToggleChip active={ragEnabled} icon={<BookOpen className="size-4" />} label="RAG" onClick={onToggleRag} />
            <ToggleChip active={webEnabled} icon={<Globe className="size-4" />} label="Search" onClick={onToggleWeb} />
            <ModelSelect model={model} models={models} onChange={onModelChange} />
            <ReasoningProfileSelect
              modelOption={selectedModelOption}
              onChange={onReasoningProfileChange}
              value={reasoningProfile}
            />
          </div>

          <ComposerVoiceButton
            disabled={voiceDisabled}
            isRecording={isRecording}
            isTranscribing={isTranscribing}
            onClick={onToggleRecording}
          />

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
            title={submitBlockedReason ?? undefined}
            type="button"
          >
            {isStreaming ? <Square className="size-3.5 fill-current" /> : <ArrowUp className="size-4" />}
          </button>
        </div>

        <div className="px-4 pb-3 pt-1 md:hidden">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <ComposerMobileToolbar
                attachmentUploadAvailable={attachmentUploadAvailable}
                attachmentsPresent={attachments.length > 0}
                isStreaming={isStreaming}
                onAddAttachment={() => inputRef.current?.click()}
                onReasoningProfileChange={onReasoningProfileChange}
                onToggleRag={onToggleRag}
                onToggleWeb={onToggleWeb}
                reasoningProfile={reasoningProfile}
                selectedModelOption={selectedModelOption}
                toolMode={toolMode}
              />
            </div>

            <div className="ml-auto flex shrink-0 items-center gap-2">
              <ComposerVoiceButton
                compact
                disabled={voiceDisabled}
                isRecording={isRecording}
                isTranscribing={isTranscribing}
                onClick={onToggleRecording}
              />

              <button
                className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-[14px] transition-colors ${
                  isStreaming
                    ? "bg-app-danger text-white hover:bg-app-danger"
                    : canSubmit
                      ? "bg-app-accent-soft text-app-accent-strong hover:bg-[#e7ddcf]"
                      : "bg-app-panel-soft text-app-muted/55"
                }`}
                disabled={!isStreaming && !canSubmit}
                onClick={isStreaming ? onStop : onSubmit}
                title={submitBlockedReason ?? undefined}
                type="button"
              >
                {isStreaming ? <Square className="size-3.5 fill-current" /> : <ArrowUp className="size-4" />}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
