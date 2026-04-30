import { Check, Copy, Globe, Pencil, RotateCcw, Square, ThumbsDown, ThumbsUp, Volume2 } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { thinkingPanelLabels } from "../../models/lib/modelCapabilities";
import { findModelOption } from "../../models/lib/modelOptions";
import { useMessageSpeechPlayback } from "../model/useMessageSpeechPlayback";
import { useSpeechPreferences } from "../../settings/model/useSpeechPreferences";
import { ASSISTANT_DRAFT_ID } from "../lib/constants";
import type { ChatMessage, FeedbackValue, ModelOption, SearchTrace } from "../../../types";
import { ContextPanel } from "./context/ContextPanel";
import { MarkdownMessage } from "./markdown/MarkdownMessage";
import { MessageAttachmentStrip } from "./message/MessageAttachmentStrip";
import { MessageSources } from "./message/MessageSources";
import { ThinkingPanel } from "./thinking/ThinkingPanel";

interface MessageListProps {
  items: ChatMessage[];
  conversationModel: string;
  editingUserMessageContent?: string;
  editingUserMessageId?: number | string | null;
  models: ModelOption[];
  isReasoningStreaming?: boolean;
  isStreaming?: boolean;
  reserveThinkingSpace?: boolean;
  onFeedback?: (messageId: number, value: FeedbackValue | null) => void;
  onCancelEditingUserMessage?: () => void;
  onChangeEditingUserMessage?: (content: string) => void;
  onRetry?: (messageId: number | string) => void;
  onStartEditingUserMessage?: (messageId: number | string) => void;
  onSubmitEditingUserMessage?: (messageId: number | string) => void;
  collapsedMessageIds?: ReadonlySet<number | string>;
  streamingStatusLabel?: string | null;
}

function StreamingLabel({ label }: { label: string }) {
  return (
    <div className="mb-3 flex min-h-[34px] items-center py-[2px]">
      <div className="inline-flex max-w-full flex-wrap items-center gap-2.5 text-app-muted/80">
        <span className="app-streaming-label inline-flex shrink-0 whitespace-nowrap text-[15px] leading-[1.4] tracking-[0.01em]">
          {label}
        </span>
        <div aria-hidden="true" className="inline-flex items-center gap-1.25 self-center">
          <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.15s_infinite]" />
          <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.3s_infinite]" />
          <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.45s_infinite]" />
        </div>
      </div>
    </div>
  );
}

function StreamingStatusSlot({
  label,
  panelLabels,
  reasoning,
  streaming,
}: {
  label: string | null;
  panelLabels: {
    streamingLabel: string;
    settledLabel: string;
  };
  reasoning: string;
  streaming: boolean;
}) {
  if (reasoning.trim()) {
    return (
      <ThinkingPanel
        settledLabel={panelLabels.settledLabel}
        streaming={streaming}
        streamingLabel={panelLabels.streamingLabel}
        trace={reasoning}
      />
    );
  }

  if (!label) {
    return null;
  }

  return <StreamingLabel label={label} />;
}

function SearchTracePanel({ trace }: { trace: SearchTrace }) {
  const queries = trace.queries.slice(0, 8);
  const sources = trace.sources.slice(0, 8);
  if (queries.length === 0 && sources.length === 0) {
    return null;
  }

  return (
    <div className="mb-4 text-[15px] leading-7 text-app-muted/82">
      <div className="mb-2 inline-flex items-center gap-2 text-app-muted/88">
        <Globe className="size-4" />
        <span>正在搜索网页</span>
      </div>
      <div className="space-y-1.5 break-words [overflow-wrap:anywhere]">
        {queries.map((query) => (
          <div key={`query-${query}`}>{query}</div>
        ))}
        {sources.map((source, index) => {
          const url = source.url?.trim();
          const title = source.title?.trim();
          return (
            <div key={`source-${url}-${index}`}>
              {title ? <span>{title} </span> : null}
              {url ? <span>{url}</span> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function pendingAssistantLabel(panelLabels: { streamingLabel: string }, hasReasoningCapability: boolean) {
  if (hasReasoningCapability) {
    return panelLabels.streamingLabel;
  }
  return "正在组织回答";
}

function renderMessageContent(content: string) {
  const blocks = content.split(/\n{2,}/).filter(Boolean);
  if (blocks.length === 0) {
    return <p> </p>;
  }

  return blocks.map((block, index) => (
    <p className={`${index === 0 ? "" : "mt-3"} break-words [overflow-wrap:anywhere]`} key={`${block}-${index}`}>
      {block}
    </p>
  ));
}

function hasLaterRenderableAssistantInSameTurn(items: ChatMessage[], startIndex: number) {
  for (let index = startIndex + 1; index < items.length; index += 1) {
    const candidate = items[index];
    if (candidate.role === "user") {
      return false;
    }

    if (candidate.role === "assistant" && candidate.content.trim()) {
      return true;
    }
  }

  return false;
}

function ActionIconButton({
  active = false,
  ariaLabel,
  children,
  disabled = false,
  onClick,
  title,
}: {
  active?: boolean;
  ariaLabel: string;
  children: ReactNode;
  disabled?: boolean;
  onClick?: () => void;
  title?: string;
}) {
  return (
    <button
      aria-label={ariaLabel}
      className={`flex h-8 w-8 items-center justify-center rounded-lg transition ${
        disabled
          ? "cursor-not-allowed text-app-muted/35"
          : active
            ? "text-app-accent-strong hover:text-app-accent-strong"
            : "text-app-muted hover:text-app-text"
      }`}
      disabled={disabled}
      onClick={onClick}
      title={title}
      type="button"
    >
      {children}
    </button>
  );
}

function AssistantActions({
  content,
  feedback,
  messageId,
  hidden = false,
  isPlaybackSupported,
  isPlaying = false,
  onFeedback,
  onTogglePlayback,
  onRetry,
}: {
  content: string;
  feedback?: FeedbackValue | null;
  messageId: number | string;
  hidden?: boolean;
  isPlaybackSupported: boolean;
  isPlaying?: boolean;
  onFeedback?: (messageId: number, value: FeedbackValue | null) => void;
  onTogglePlayback?: (messageId: number | string, content: string) => void | Promise<unknown>;
  onRetry?: (messageId: number | string) => void;
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

  if (hidden) {
    return <div aria-hidden="true" className="mt-3 h-8" />;
  }

  return (
    <div className="mt-3 flex items-center gap-3 text-app-muted">
      <ActionIconButton ariaLabel="Copy response" onClick={() => void handleCopy()}>
        {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
      </ActionIconButton>
      <ActionIconButton
        ariaLabel="Good response"
        onClick={() =>
          typeof messageId === "number" ? onFeedback?.(messageId, feedback === "up" ? null : "up") : undefined
        }
      >
        <ThumbsUp className={`size-4 ${feedback === "up" ? "fill-current text-app-accent-strong" : ""}`} />
      </ActionIconButton>
      <ActionIconButton
        ariaLabel="Bad response"
        onClick={() =>
          typeof messageId === "number" ? onFeedback?.(messageId, feedback === "down" ? null : "down") : undefined
        }
      >
        <ThumbsDown className={`size-4 ${feedback === "down" ? "fill-current text-[#9d3d32]" : ""}`} />
      </ActionIconButton>
      <ActionIconButton
        ariaLabel="Retry response"
        onClick={() => onRetry?.(messageId)}
      >
        <RotateCcw className="size-4" />
      </ActionIconButton>
      <ActionIconButton
        active={isPlaying}
        ariaLabel={isPlaying ? "Stop playback" : "Play response"}
        disabled={!isPlaybackSupported}
        onClick={() => void onTogglePlayback?.(messageId, content)}
        title={isPlaybackSupported ? undefined : "Speech playback is not supported in this browser."}
      >
        {isPlaying ? <Square className="size-3.5 fill-current" /> : <Volume2 className="size-4" />}
      </ActionIconButton>
    </div>
  );
}

function UserActions({
  content,
  messageId,
  hidden = false,
  onEdit,
}: {
  content: string;
  messageId: number | string;
  hidden?: boolean;
  onEdit?: (messageId: number | string) => void;
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

  if (!content.trim()) {
    return null;
  }

  if (hidden) {
    return <div aria-hidden="true" className="mt-1 mb-3 h-9" />;
  }

  return (
    <div className="mt-1 mb-3 flex items-center justify-end gap-1 text-app-muted">
      <button
        aria-label="Edit message"
        className="flex h-9 w-9 items-center justify-center rounded-xl text-app-muted transition hover:text-app-text"
        onClick={() => onEdit?.(messageId)}
        type="button"
      >
        <Pencil className="size-4" />
      </button>
      <button
        aria-label="Copy message"
        className="flex h-9 w-9 items-center justify-center rounded-xl text-app-muted transition hover:text-app-text"
        onClick={() => void handleCopy()}
        type="button"
      >
        {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
      </button>
    </div>
  );
}

function InlineUserMessageEditor({
  messageId,
  onCancel,
  onChange,
  onSubmit,
  value,
}: {
  messageId: number | string;
  onCancel?: () => void;
  onChange?: (content: string) => void;
  onSubmit?: (messageId: number | string) => void;
  value: string;
}) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }

    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
  }, []);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }

    textarea.style.height = "0px";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [value]);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel?.();
      return;
    }

    if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && !event.nativeEvent.isComposing) {
      event.preventDefault();
      onSubmit?.(messageId);
    }
  }

  return (
    <div className="min-w-0 rounded-[20px] bg-app-panel-soft px-6 py-4 text-left text-app-accent-strong">
      <textarea
        aria-label="Edit message"
        className="min-h-[96px] w-full resize-none overflow-hidden border-none bg-transparent text-[15px] leading-7 text-app-accent-strong outline-none placeholder:text-app-muted/60"
        onChange={(event) => onChange?.(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Edit your message"
        ref={textareaRef}
        rows={1}
        value={value}
      />
      <div className="mt-3 flex items-center justify-end gap-2">
        <button
          className="inline-flex h-9 items-center rounded-lg border border-app-border/80 bg-white/70 px-3 text-sm text-app-muted transition hover:border-app-border-strong hover:text-app-text"
          onClick={onCancel}
          type="button"
        >
          Cancel
        </button>
        <button
          className="inline-flex h-9 items-center rounded-lg bg-app-accent px-3 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!value.trim()}
          onClick={() => onSubmit?.(messageId)}
          type="button"
        >
          Update
        </button>
      </div>
    </div>
  );
}

export function MessageList({
  items,
  conversationModel,
  editingUserMessageContent = "",
  editingUserMessageId = null,
  models,
  isReasoningStreaming = false,
  isStreaming = false,
  reserveThinkingSpace = false,
  onFeedback,
  onCancelEditingUserMessage,
  onChangeEditingUserMessage,
  onRetry,
  onStartEditingUserMessage,
  onSubmitEditingUserMessage,
  collapsedMessageIds,
  streamingStatusLabel = null,
}: MessageListProps) {
  const { preferences } = useSpeechPreferences();
  const {
    isSupported: isSpeechPlaybackSupported,
    playingMessageId,
    stopPlayback,
    togglePlayback,
  } = useMessageSpeechPlayback(preferences);
  const activeStreamingAssistantId = isStreaming
    ? [...items].reverse().find((item) => item.role === "assistant")?.id
    : null;
  const previousStreamingRef = useRef(isStreaming);

  useEffect(() => {
    if (playingMessageId == null) {
      return;
    }

    if (!items.some((item) => item.id === playingMessageId)) {
      stopPlayback();
    }
  }, [items, playingMessageId, stopPlayback]);

  useEffect(() => {
    if (!isStreaming) {
      return;
    }
    stopPlayback();
  }, [isStreaming, stopPlayback]);

  useEffect(() => {
    const wasStreaming = previousStreamingRef.current;
    previousStreamingRef.current = isStreaming;

    if (!wasStreaming || isStreaming || !preferences.autoPlayAssistant || playingMessageId != null) {
      return;
    }

    const latestAssistant = [...items].reverse().find(
      (item) => item.role === "assistant" && item.content.trim() && item.localStatus !== "stopped",
    );
    if (!latestAssistant) {
      return;
    }

    void togglePlayback(latestAssistant.id, latestAssistant.content);
  }, [isStreaming, items, playingMessageId, preferences.autoPlayAssistant, togglePlayback]);

  return (
    <div className="flex w-full flex-col pb-6">
      {items.map((item, index) => {
        if (collapsedMessageIds?.has(item.id)) {
          return null;
        }

        const isAssistant = item.role === "assistant";
        const isEmptyAssistant = isAssistant && !item.content.trim();
        const hasStoppedNote = item.localStatus === "stopped";
        const isActiveStreamingAssistant = item.id === activeStreamingAssistantId;
        const reasoning = item.reasoning ?? "";
        const messageModelOption = isAssistant
          ? findModelOption(models, item.model ?? conversationModel)
          : null;
        const panelLabels = thinkingPanelLabels(messageModelOption);
        const hasReasoningCapability = Boolean(
          messageModelOption?.supports_thinking_trace || messageModelOption?.supports_thinking,
        );
        const showThinkingPanel = reasoning.trim().length > 0;
        const thinkingStreaming = isActiveStreamingAssistant && isReasoningStreaming;
        const showStreamingStatus = isActiveStreamingAssistant && isEmptyAssistant && Boolean(streamingStatusLabel);
        const isPendingAssistantDraft = item.id === ASSISTANT_DRAFT_ID && isEmptyAssistant && !hasStoppedNote;
        const showPendingPlaceholder =
          !hasStoppedNote &&
          !showThinkingPanel &&
          !showStreamingStatus &&
          (isPendingAssistantDraft || (isActiveStreamingAssistant && reserveThinkingSpace));
        const showSources = !isEmptyAssistant && item.id !== activeStreamingAssistantId;
        const showSearchTrace = Boolean(isActiveStreamingAssistant && item.search_trace);
        const attachments = item.attachments ?? [];
        const isEditingUserMessage = !isAssistant && editingUserMessageId === item.id;
        const shouldHideOrphanReasoningMessage =
          isAssistant
          && isEmptyAssistant
          && showThinkingPanel
          && !isActiveStreamingAssistant
          && !hasStoppedNote
          && hasLaterRenderableAssistantInSameTurn(items, index);

        if (!isAssistant) {
          return (
            <article className="mb-4 flex justify-end last:mb-0" key={item.clientKey ?? String(item.id)}>
              <div
                className={
                  isEditingUserMessage
                    ? "w-full"
                    : "group flex w-fit max-w-[420px] flex-col items-end"
                }
              >
                <MessageAttachmentStrip align="end" attachments={attachments} />
                {isEditingUserMessage ? (
                  <InlineUserMessageEditor
                    messageId={item.id}
                    onCancel={onCancelEditingUserMessage}
                    onChange={onChangeEditingUserMessage}
                    onSubmit={onSubmitEditingUserMessage}
                    value={editingUserMessageContent}
                  />
                ) : item.content.trim() ? (
                  <div className="w-fit max-w-full min-w-0 self-end rounded-[18px] bg-app-panel-soft px-4 py-1.75 text-left text-[15px] leading-7 text-app-accent-strong">
                    {renderMessageContent(item.content)}
                  </div>
                ) : null}
                {!isEditingUserMessage ? (
                  <UserActions
                    content={item.content}
                    hidden={false}
                    messageId={item.id}
                    onEdit={onStartEditingUserMessage}
                  />
                ) : null}
              </div>
            </article>
          );
        }

        if (isEmptyAssistant && !showThinkingPanel && !showStreamingStatus && !showPendingPlaceholder && !hasStoppedNote) {
          return null;
        }

        if (shouldHideOrphanReasoningMessage) {
          return null;
        }

        return (
          <article className="mb-5 flex justify-start last:mb-0" key={item.clientKey ?? String(item.id)}>
            <div className="w-full">
              {showThinkingPanel ? (
                <StreamingStatusSlot
                  label={null}
                  panelLabels={panelLabels}
                  reasoning={reasoning}
                  streaming={thinkingStreaming}
                />
              ) : showStreamingStatus ? (
                <StreamingStatusSlot
                  label={streamingStatusLabel}
                  panelLabels={panelLabels}
                  reasoning=""
                  streaming={false}
                />
              ) : showPendingPlaceholder ? (
                <StreamingStatusSlot
                  label={pendingAssistantLabel(panelLabels, reserveThinkingSpace || hasReasoningCapability)}
                  panelLabels={panelLabels}
                  reasoning=""
                  streaming={false}
                />
              ) : null}

              {showSearchTrace ? <SearchTracePanel trace={item.search_trace as SearchTrace} /> : null}

              {!isEmptyAssistant ? (
                <div className="text-[15px] leading-8 text-app-text">
                  <MarkdownMessage content={item.content} />
                </div>
              ) : null}

              {hasStoppedNote ? (
                <div className={`text-[15px] italic text-app-muted/88 ${isEmptyAssistant ? "mt-1" : "mt-4"}`}>
                  You stopped this response
                </div>
              ) : null}

              {showSources ? <MessageSources sources={item.sources ?? []} /> : null}

              {item.context ? <ContextPanel context={item.context} /> : null}

              {!isEmptyAssistant ? (
                <AssistantActions
                  content={item.content}
                  feedback={item.feedback}
                  hidden={item.id === activeStreamingAssistantId}
                  isPlaybackSupported={isSpeechPlaybackSupported}
                  isPlaying={playingMessageId === item.id}
                  messageId={item.id}
                  onFeedback={onFeedback}
                  onTogglePlayback={togglePlayback}
                  onRetry={onRetry}
                />
              ) : null}
            </div>
          </article>
        );
      })}
    </div>
  );
}
