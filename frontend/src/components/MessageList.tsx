import { Check, Copy, CornerUpLeft, RotateCcw, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { ChatMessage } from "../types";
import { MarkdownMessage } from "./markdown/MarkdownMessage";
import { MessageAttachmentStrip } from "./message/MessageAttachmentStrip";
import { MessageSources } from "./message/MessageSources";
import { ThinkingPanel } from "./thinking/ThinkingPanel";

interface MessageListProps {
  items: ChatMessage[];
  isStreaming?: boolean;
  onRetry?: (messageId: number | string) => void;
  onReuseUserMessage?: (content: string) => void;
  collapsedMessageIds?: ReadonlySet<number | string>;
  streamingStatusLabel?: string | null;
  thinkingTrace?: string;
  thinkingTraceExpanded?: boolean;
  onToggleThinkingTrace?: () => void;
}

function StreamingLabel({ label }: { label: string }) {
  return (
    <div className="mb-3 flex min-h-[34px] items-center py-[2px]">
      <div className="inline-flex items-center gap-2.5 text-app-muted/80">
        <span className="app-streaming-label text-[15px] italic tracking-[0.01em]">{label}</span>
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
  thinkingTrace,
  thinkingTraceExpanded,
  onToggleThinkingTrace,
}: {
  label: string | null;
  thinkingTrace: string;
  thinkingTraceExpanded: boolean;
  onToggleThinkingTrace?: () => void;
}) {
  if (thinkingTrace.trim()) {
    return (
      <ThinkingPanel
        expanded={thinkingTraceExpanded}
        onToggle={() => onToggleThinkingTrace?.()}
        trace={thinkingTrace}
      />
    );
  }

  if (!label) {
    return null;
  }

  return <StreamingLabel label={label} />;
}

function renderMessageContent(content: string) {
  const blocks = content.split(/\n{2,}/).filter(Boolean);
  if (blocks.length === 0) {
    return <p> </p>;
  }

  return blocks.map((block, index) => (
    <p className={index === 0 ? "" : "mt-3"} key={`${block}-${index}`}>
      {block}
    </p>
  ));
}

function ActionIconButton({
  ariaLabel,
  children,
  onClick,
}: {
  ariaLabel: string;
  children: ReactNode;
  onClick?: () => void;
}) {
  return (
    <button
      aria-label={ariaLabel}
      className="flex h-8 w-8 items-center justify-center rounded-lg text-app-muted transition hover:text-app-text"
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  );
}

function AssistantActions({
  content,
  messageId,
  hidden = false,
  onRetry,
}: {
  content: string;
  messageId: number | string;
  hidden?: boolean;
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
    return null;
  }

  return (
    <div className="mt-3 flex items-center gap-3 text-app-muted">
      <ActionIconButton ariaLabel="Copy response" onClick={() => void handleCopy()}>
        {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
      </ActionIconButton>
      <ActionIconButton ariaLabel="Good response">
        <ThumbsUp className="size-4" />
      </ActionIconButton>
      <ActionIconButton ariaLabel="Bad response">
        <ThumbsDown className="size-4" />
      </ActionIconButton>
      <ActionIconButton
        ariaLabel="Retry response"
        onClick={() => onRetry?.(messageId)}
      >
        <RotateCcw className="size-4" />
      </ActionIconButton>
    </div>
  );
}

function UserActions({
  content,
  hidden = false,
  onReuse,
}: {
  content: string;
  hidden?: boolean;
  onReuse?: (content: string) => void;
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

  if (hidden || !content.trim()) {
    return null;
  }

  return (
    <div className="mt-1 mb-3 flex items-center justify-end gap-1 opacity-0 transition duration-150 group-hover:opacity-100">
      <button
        aria-label="Reuse message"
        className="flex h-9 w-9 items-center justify-center rounded-xl text-app-muted transition hover:text-app-text"
        onClick={() => onReuse?.(content)}
        type="button"
      >
        <CornerUpLeft className="size-4" />
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

export function MessageList({
  items,
  isStreaming = false,
  onRetry,
  onReuseUserMessage,
  collapsedMessageIds,
  streamingStatusLabel = null,
  thinkingTrace = "",
  thinkingTraceExpanded = false,
  onToggleThinkingTrace,
}: MessageListProps) {
  const activeStreamingAssistantId = isStreaming
    ? [...items].reverse().find((item) => item.role === "assistant")?.id
    : null;
  const hideActions = isStreaming;

  return (
    <div className="mx-auto flex w-full max-w-[920px] flex-col pb-6">
      {items.map((item) => {
        if (collapsedMessageIds?.has(item.id)) {
          return null;
        }

        const isAssistant = item.role === "assistant";
        const isEmptyAssistant = isAssistant && !item.content.trim();
        const hasStoppedNote = item.localStatus === "stopped";
        const isActiveStreamingAssistant = item.id === activeStreamingAssistantId;
        const hasThinkingTrace = isActiveStreamingAssistant && thinkingTrace.trim().length > 0;
        const showStreamingStatus =
          isActiveStreamingAssistant &&
          isEmptyAssistant &&
          (hasThinkingTrace || Boolean(streamingStatusLabel));
        const showSources = !isEmptyAssistant && item.id !== activeStreamingAssistantId;
        const attachments = item.attachments ?? [];

        if (!isAssistant) {
          return (
            <article className="mb-4 flex justify-end last:mb-0" key={item.id}>
              <div className="group max-w-[420px]">
                <MessageAttachmentStrip align="end" attachments={attachments} />
                {item.content.trim() ? (
                  <div className="rounded-[20px] bg-app-panel-soft px-4 py-2.5 text-left text-[15px] leading-7 text-app-accent-strong">
                    {renderMessageContent(item.content)}
                  </div>
                ) : null}
                <UserActions content={item.content} hidden={hideActions} onReuse={onReuseUserMessage} />
              </div>
            </article>
          );
        }

        if (isEmptyAssistant && !showStreamingStatus && !hasStoppedNote) {
          return null;
        }

        return (
          <article className="mb-5 flex justify-start last:mb-0" key={item.id}>
            <div className="w-full max-w-[760px]">
              {showStreamingStatus ? (
                <StreamingStatusSlot
                  label={streamingStatusLabel}
                  onToggleThinkingTrace={onToggleThinkingTrace}
                  thinkingTrace={isActiveStreamingAssistant ? thinkingTrace : ""}
                  thinkingTraceExpanded={thinkingTraceExpanded}
                />
              ) : null}

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

              {!isEmptyAssistant ? (
                <AssistantActions
                  content={item.content}
                  hidden={hideActions || item.id === activeStreamingAssistantId}
                  messageId={item.id}
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
