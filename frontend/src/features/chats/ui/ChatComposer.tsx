import {
  ArrowUp,
  BookOpen,
  ChevronUp,
  Check,
  FolderInput,
  Globe,
  Image,
  LoaderCircle,
  Mic,
  Paperclip,
  Plus,
  Scale,
  Square,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type ClipboardEvent, type ChangeEvent, type DragEvent, type KeyboardEvent, type ReactNode } from "react";

import { findModelOption } from "../../models/lib/modelOptions";
import {
  IMAGE_SIZE_OPTIONS,
  imageSizeChoiceForValue,
} from "../lib/imageSizeOptions";
import type { ComposerAttachmentDraft } from "../model/useComposerAttachments";
import type { ComposerMode, ModelOption, ReasoningProfileValue, ToolMode } from "../../../types";
import { ComposerAttachmentStrip } from "./composer/ComposerAttachmentStrip";
import { ComposerMobileToolbar } from "./composer/ComposerMobileToolbar";
import { ModelSelect } from "../../models/ui/ModelSelect";
import { ReasoningProfileSelect } from "../../models/ui/ReasoningProfileSelect";
import { cn, sidebarMenuPanelClass } from "../../workspace/ui/sidebar/styles";

const IMAGE_ATTACHMENT_ACCEPT = [
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
];

const FILE_ATTACHMENT_ACCEPT = [
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
];

const ATTACHMENT_ACCEPT = [...IMAGE_ATTACHMENT_ACCEPT, ...FILE_ATTACHMENT_ACCEPT].join(",");
const FILE_ONLY_ATTACHMENT_ACCEPT = FILE_ATTACHMENT_ACCEPT.join(",");

interface ChatComposerProps {
  value: string;
  attachments: ComposerAttachmentDraft[];
  onChange: (value: string) => void;
  onSelectAttachments: (files: FileList | File[]) => void;
  onRemoveAttachment: (attachmentId: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  onNewDebate: () => void;
  isRecording: boolean;
  isStreaming: boolean;
  isTranscribing: boolean;
  model: string;
  models: ModelOption[];
  onModelChange: (value: string) => void;
  composerMode: ComposerMode;
  imageSize: string;
  onImageSizeChange: (value: string) => void;
  onComposerModeChange: (value: ComposerMode) => void;
  reasoningProfile: ReasoningProfileValue;
  onReasoningProfileChange: (value: ReasoningProfileValue) => void;
  toolMode: ToolMode;
  knowledgeFolders: string[];
  knowledgeFolder: string;
  onKnowledgeFolderChange: (value: string) => void;
  submitBlocked: boolean;
  submitBlockedReason: string | null;
  attachmentUploadAvailable: boolean;
  onToggleRag: () => void;
  onToggleWeb: () => void;
  onToggleRecording: () => void;
  centered?: boolean;
}

const ROOT_KNOWLEDGE_FOLDER_VALUE = "__root__";
const INLINE_SELECT_BUTTON_CLASS =
  "inline-flex h-10 min-w-0 items-center rounded-[8px] border border-app-border bg-app-panel-strong px-3 text-left text-[14px] font-medium tracking-[-0.02em] text-[#5f564a] transition hover:bg-app-panel-soft";
const INLINE_SELECT_ITEM_CLASS =
  "flex h-10 w-full items-center justify-between gap-3 px-3 py-0 text-left text-[14px] font-medium tracking-[-0.02em] transition-colors focus:outline-none focus-visible:outline-none";

function knowledgeFolderLeaf(value: string): string {
  const parts = value.split("/").filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : value;
}

function knowledgeFolderFullLabel(value: string): string {
  if (!value) {
    return "全部知识库";
  }
  if (value === ROOT_KNOWLEDGE_FOLDER_VALUE) {
    return "默认分组";
  }
  return value;
}

function knowledgeFolderShortLabel(value: string): string {
  if (!value) {
    return "全部";
  }
  if (value === ROOT_KNOWLEDGE_FOLDER_VALUE) {
    return "默认";
  }
  return knowledgeFolderLeaf(value);
}

function KnowledgeScopeMenu({
  compact = false,
  disabled,
  folders,
  value,
  onChange,
}: {
  compact?: boolean;
  disabled: boolean;
  folders: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const options = [
    { label: "全部知识库", value: "" },
    { label: "默认分组", value: ROOT_KNOWLEDGE_FOLDER_VALUE },
    ...folders.map((folder) => ({ label: folder, value: folder })),
  ];
  const selectedLabel = compact ? knowledgeFolderShortLabel(value) : knowledgeFolderFullLabel(value);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: globalThis.KeyboardEvent) {
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

  return (
    <div className={cn("relative min-w-0", compact ? "w-10 shrink-0" : "shrink-0")} ref={menuRef}>
      <button
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={`知识库范围：${knowledgeFolderFullLabel(value)}`}
        className={cn(
          INLINE_SELECT_BUTTON_CLASS,
          "relative",
          compact ? "w-10 justify-center px-0" : "min-w-[150px] max-w-[240px] justify-between gap-2",
          disabled
            ? "cursor-not-allowed text-app-muted/45 hover:bg-app-panel-strong"
            : open
              ? "border-app-border-strong bg-app-panel-soft text-app-text"
              : "hover:text-app-text",
        )}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        title={`知识库范围：${knowledgeFolderFullLabel(value)}`}
        type="button"
      >
        {compact ? (
          <FolderInput className="size-4 shrink-0" />
        ) : (
          <span className="flex min-w-0 items-center gap-1.5">
            <span className="shrink-0 whitespace-nowrap text-[#5f564a]">知识库:</span>
            <span className="min-w-0 truncate text-[#5f564a]">{selectedLabel}</span>
          </span>
        )}
        {compact ? (
          value ? <span className="absolute right-2 top-2 size-1.5 rounded-full bg-app-accent-strong" /> : null
        ) : (
          <ChevronUp className={`size-4 shrink-0 text-[#5f564a] transition-transform ${open ? "" : "rotate-180"}`} />
        )}
      </button>

      {open ? (
        <div
          className={cn(
            `absolute bottom-[calc(100%+8px)] left-0 z-20 max-h-[260px] overflow-y-auto ${sidebarMenuPanelClass}`,
            compact ? "w-[min(240px,calc(100vw-2rem))]" : "min-w-full sm:w-max sm:max-w-[280px]",
          )}
          role="listbox"
        >
          {options.map((option) => {
            const selected = option.value === value;
            return (
              <button
                aria-selected={selected}
                className={cn(
                  INLINE_SELECT_ITEM_CLASS,
                  selected
                    ? "bg-app-panel-soft text-app-text"
                    : "bg-app-panel-strong text-[#5f564a] hover:bg-app-panel-soft hover:text-app-text",
                )}
                key={option.value || "all"}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                role="option"
                type="button"
              >
                <span className="min-w-0 truncate">{option.label}</span>
                {selected ? <Check className="size-4 shrink-0 text-[#5b4128]" /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function ComposerToolsMenu({
  attachmentUploadAvailable,
  disabled,
  mode,
  toolMode,
  onAddAttachment,
  onComposerModeChange,
  onNewDebate,
  onToggleRag,
  onToggleWeb,
}: {
  attachmentUploadAvailable: boolean;
  disabled: boolean;
  mode: ComposerMode;
  toolMode: ToolMode;
  onAddAttachment: () => void;
  onComposerModeChange: (value: ComposerMode) => void;
  onNewDebate: () => void;
  onToggleRag: () => void;
  onToggleWeb: () => void;
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const isImageMode = mode === "image";
  const uploadDisabled = disabled || isImageMode || !attachmentUploadAvailable;
  const ragActive = !isImageMode && toolMode === "knowledge";
  const webActive = !isImageMode && toolMode === "search";
  const toolActive = isImageMode || ragActive || webActive;

  const handleToggleImageMode = () => {
    onComposerModeChange(isImageMode ? "chat" : "image");
  };

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, []);

  const options: Array<{
    active?: boolean;
    disabled?: boolean;
    icon: ReactNode;
    label: string;
    onClick: () => void;
  }> = [
    {
      disabled: uploadDisabled,
      icon: <Paperclip className="size-4" />,
      label: "上传照片和文件",
      onClick: onAddAttachment,
    },
    {
      active: isImageMode,
      disabled,
      icon: <Image className="size-4" />,
      label: "创建图片",
      onClick: handleToggleImageMode,
    },
    {
      disabled,
      icon: <Scale className="size-4" />,
      label: "新建辩论",
      onClick: onNewDebate,
    },
    {
      active: ragActive,
      disabled: disabled || isImageMode,
      icon: <BookOpen className="size-4" />,
      label: "知识库",
      onClick: onToggleRag,
    },
    {
      active: webActive,
      disabled: disabled || isImageMode,
      icon: <Globe className="size-4" />,
      label: "网页搜索",
      onClick: onToggleWeb,
    },
  ];

  return (
    <div className="relative shrink-0" ref={menuRef}>
      <button
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="打开工具菜单"
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px] border transition-colors ${
          disabled
            ? "cursor-not-allowed border-app-border bg-transparent text-app-muted/45"
            : open || toolActive
              ? "border-app-border-strong bg-transparent text-app-text"
              : "border-app-border bg-transparent text-app-muted hover:text-app-text"
        }`}
        disabled={disabled}
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <Plus className={`size-4 transition-transform ${open ? "rotate-45" : ""}`} />
      </button>

      {open ? (
        <div className="absolute bottom-[calc(100%+10px)] left-0 z-20 w-52 overflow-hidden rounded-lg border border-app-border bg-app-panel-strong shadow-[0_18px_40px_rgba(39,28,18,0.14)]">
          {options.map((option) => {
            return (
              <button
                aria-pressed={option.active}
                className={`flex h-10 w-full items-center justify-between gap-3 px-3 text-left text-[14px] font-medium transition-colors ${
                  option.disabled
                    ? "cursor-not-allowed text-app-muted/45"
                    : option.active
                      ? "bg-app-panel-soft text-app-text"
                      : "text-app-muted hover:bg-app-panel-soft hover:text-app-text"
                }`}
                disabled={option.disabled}
                key={option.label}
                onClick={() => {
                  option.onClick();
                  setOpen(false);
                }}
                type="button"
              >
                <span className="flex min-w-0 items-center gap-3">
                  <span className="flex size-4 shrink-0 items-center justify-center">{option.icon}</span>
                  <span className="truncate">{option.label}</span>
                </span>
                {option.active ? <Check className="size-4 shrink-0 text-[#5b4128]" /> : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function ImageModePill({ disabled, onCancel }: { disabled: boolean; onCancel: () => void }) {
  return (
    <button
      aria-label="取消图片模式"
      className={`group inline-flex h-10 shrink-0 items-center gap-2 rounded-[8px] border border-app-border bg-app-panel-strong px-3 text-[14px] font-medium text-app-muted transition-colors ${
        disabled ? "cursor-not-allowed opacity-55" : "hover:bg-app-panel-soft hover:text-app-text"
      }`}
      disabled={disabled}
      onClick={onCancel}
      type="button"
    >
      <span className="flex size-4 items-center justify-center">
        <Image className="size-4 group-hover:hidden" />
        <X className="hidden size-4 group-hover:block" />
      </span>
      <span>创建图片</span>
    </button>
  );
}

function ImageSizeControl({
  compact = false,
  disabled,
  labelOnly = false,
  value,
  onChange,
}: {
  compact?: boolean;
  disabled: boolean;
  labelOnly?: boolean;
  value: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const selectedChoice = imageSizeChoiceForValue(value);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    function handleKeyDown(event: globalThis.KeyboardEvent) {
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

  return (
    <div className={cn("relative min-w-0", compact && !labelOnly ? "w-full" : "shrink-0")} ref={menuRef}>
      <button
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label="图片尺寸"
        className={cn(
          INLINE_SELECT_BUTTON_CLASS,
          "gap-2",
          labelOnly ? "min-w-[78px] justify-between" : compact ? "w-full justify-between" : "min-w-[150px] justify-between",
          disabled
            ? "cursor-not-allowed opacity-55 hover:bg-app-panel-strong"
            : open
              ? "bg-app-panel-soft"
              : "",
        )}
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className="shrink-0 whitespace-nowrap text-[#5f564a]">{labelOnly ? "尺寸" : "尺寸:"}</span>
          {labelOnly ? null : <span className="min-w-0 truncate text-[#5f564a]">{selectedChoice.label}</span>}
        </span>
        <ChevronUp className={`size-4 shrink-0 text-[#5f564a] transition-transform ${open ? "" : "rotate-180"}`} />
      </button>

      {open ? (
        <div
          className={cn(
            `absolute bottom-[calc(100%+8px)] left-0 z-20 min-w-full ${sidebarMenuPanelClass}`,
            labelOnly ? "w-[min(170px,calc(100vw-2rem))]" : "sm:w-max sm:max-w-[190px]",
          )}
        >
          <div className="max-h-[210px] overflow-y-auto" role="listbox">
            {IMAGE_SIZE_OPTIONS.map((choice) => {
              const selected = choice.value === selectedChoice.value;
              return (
                <button
                  aria-selected={selected}
                  className={cn(
                    INLINE_SELECT_ITEM_CLASS,
                    selected
                      ? "bg-app-panel-soft text-[#5f564a]"
                      : "bg-app-panel-strong text-[#5f564a] hover:bg-app-panel-soft",
                  )}
                  key={choice.value}
                  onClick={() => {
                    onChange(choice.value);
                    setOpen(false);
                  }}
                  role="option"
                  type="button"
                >
                  <span className="min-w-0 truncate">{choice.label}</span>
                  {selected ? <Check className="size-4 shrink-0 text-[#5f564a]" /> : null}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
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
  const sizeClassName = compact ? "h-10 w-10 rounded-[8px]" : "h-10 w-10 rounded-[8px]";
  const iconClassName = "size-4";
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
        <Square className="size-3.5 fill-current" />
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
  onNewDebate,
  isRecording,
  isStreaming,
  isTranscribing,
  model,
  models,
  onModelChange,
  composerMode,
  imageSize,
  onImageSizeChange,
  onComposerModeChange,
  reasoningProfile,
  onReasoningProfileChange,
  toolMode,
  knowledgeFolders,
  knowledgeFolder,
  onKnowledgeFolderChange,
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
  const imageMode = composerMode === "image";
  const showKnowledgeScope = !imageMode && toolMode === "knowledge";
  const voiceDisabled = isStreaming || isTranscribing;
  const selectedModelOption = findModelOption(models, model);
  const attachmentAccept = selectedModelOption.capabilities?.input.image === false
    ? FILE_ONLY_ATTACHMENT_ACCEPT
    : ATTACHMENT_ACCEPT;

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (isStreaming || canSubmit) {
        isStreaming ? onStop() : onSubmit();
      }
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    if (imageMode || !attachmentUploadAvailable || isStreaming || !event.clipboardData) {
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
    if (imageMode || !attachmentUploadAvailable || isStreaming || event.dataTransfer.files.length === 0) {
      return;
    }
    event.preventDefault();
    setDragActive(true);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    if (imageMode || !attachmentUploadAvailable || isStreaming || event.dataTransfer.files.length === 0) {
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
    if (imageMode || !attachmentUploadAvailable || isStreaming || event.dataTransfer.files.length === 0) {
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
          accept={attachmentAccept}
          className="hidden"
          multiple
          onChange={handleSelectAttachments}
          ref={inputRef}
          type="file"
        />

        <ComposerAttachmentStrip attachments={attachments} onRemove={onRemoveAttachment} />

        <textarea
          className="min-h-[72px] max-h-[220px] w-full resize-none overflow-y-auto bg-transparent px-3 py-3 text-[16px] leading-7 text-app-text placeholder:text-[#9a9387] [field-sizing:fixed] md:min-h-24 md:px-4 md:py-4"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={imageMode ? "描述你想生成的图片" : "Ask anything"}
          rows={centered ? 3 : 2}
          title={submitBlockedReason ?? undefined}
          value={value}
        />

        {dragActive ? (
          <div className="pointer-events-none absolute inset-0 rounded-lg border border-dashed border-app-accent-strong bg-[rgba(248,242,233,0.82)]" />
        ) : null}

        <div className="hidden items-center gap-3 px-4 py-3 md:flex">
          <div className="flex min-w-0 flex-1 items-center gap-2 overflow-visible">
            <ComposerToolsMenu
              attachmentUploadAvailable={attachmentUploadAvailable}
              disabled={isStreaming}
              mode={composerMode}
              onAddAttachment={() => inputRef.current?.click()}
              onComposerModeChange={onComposerModeChange}
              onNewDebate={onNewDebate}
              onToggleRag={onToggleRag}
              onToggleWeb={onToggleWeb}
              toolMode={toolMode}
            />
            {imageMode ? (
              <ImageModePill disabled={isStreaming} onCancel={() => onComposerModeChange("chat")} />
            ) : null}
            {imageMode ? (
              <ImageSizeControl disabled={isStreaming} onChange={onImageSizeChange} value={imageSize} />
            ) : null}
            {!imageMode ? <ModelSelect model={model} models={models} onChange={onModelChange} /> : null}
            {!imageMode ? (
              <ReasoningProfileSelect
                modelOption={selectedModelOption}
                onChange={onReasoningProfileChange}
                value={reasoningProfile}
              />
            ) : null}
            {showKnowledgeScope ? (
              <KnowledgeScopeMenu
                disabled={isStreaming}
                folders={knowledgeFolders}
                onChange={onKnowledgeFolderChange}
                value={knowledgeFolder}
              />
            ) : null}
          </div>

          <ComposerVoiceButton
            disabled={voiceDisabled}
            isRecording={isRecording}
            isTranscribing={isTranscribing}
            onClick={onToggleRecording}
          />

          <button
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px] transition-colors ${
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

        <div className="px-3 pb-3 pt-1 md:hidden">
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-1.5">
              <ComposerMobileToolbar
                attachmentUploadAvailable={attachmentUploadAvailable && !imageMode}
                attachmentsPresent={attachments.length > 0}
                isStreaming={isStreaming}
                onAddAttachment={() => inputRef.current?.click()}
                onNewDebate={onNewDebate}
                onReasoningProfileChange={onReasoningProfileChange}
                composerMode={composerMode}
                onComposerModeChange={onComposerModeChange}
                imageSizeControl={
                  imageMode ? (
                    <ImageSizeControl
                      disabled={isStreaming}
                      labelOnly
                      onChange={onImageSizeChange}
                      value={imageSize}
                    />
                  ) : null
                }
                onToggleRag={onToggleRag}
                onToggleWeb={onToggleWeb}
                reasoningProfile={reasoningProfile}
                selectedModelOption={selectedModelOption}
                toolMode={toolMode}
              />
              {showKnowledgeScope ? (
                <KnowledgeScopeMenu
                  compact
                  disabled={isStreaming}
                  folders={knowledgeFolders}
                  onChange={onKnowledgeFolderChange}
                  value={knowledgeFolder}
                />
              ) : null}
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
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-[8px] transition-colors ${
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
