import { Check, Copy, RotateCcw, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { ChatMessage, ToolPlan } from "../types";
import { MarkdownMessage } from "./markdown/MarkdownMessage";
import { MessageImageStrip } from "./message/MessageImageStrip";
import { MessageSources } from "./message/MessageSources";
import { ToolPlanPanel } from "./message/ToolPlanPanel";
import { ThinkingPanel } from "./thinking/ThinkingPanel";

interface MessageListProps {
  items: ChatMessage[];
  isStreaming?: boolean;
  onRetry?: (messageId: number) => void;
  collapsedMessageIds?: ReadonlySet<number | string>;
  statusItems?: string[];
  toolPlan?: ToolPlan | null;
  thinkingEnabled?: boolean;
  thinkingTrace?: string;
  thinkingTraceAvailable?: boolean;
  thinkingTraceExpanded?: boolean;
  onToggleThinkingTrace?: () => void;
}

function ActivityIndicator({ label }: { label: string }) {
  return (
    <div className="inline-flex items-center gap-2.5 leading-none text-app-muted/80">
      <span className="animate-[thinking-dot_1.8s_ease-in-out_infinite] text-[15px] italic tracking-[0.01em]">
        {label}
      </span>
      <div aria-hidden="true" className="inline-flex items-center gap-1.25 self-center">
        <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.15s_infinite]" />
        <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.3s_infinite]" />
        <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.45s_infinite]" />
      </div>
    </div>
  );
}

function StreamingStatusList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="mb-2 space-y-2">
      {items.map((item) => (
        <ActivityIndicator key={item} label={item} />
      ))}
    </div>
  );
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
  onRetry?: (messageId: number) => void;
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
        onClick={() => {
          if (typeof messageId === "number") {
            onRetry?.(messageId);
          }
        }}
      >
        <RotateCcw className="size-4" />
      </ActionIconButton>
    </div>
  );
}

function UserActions({ content, hidden = false }: { content: string; hidden?: boolean }) {
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
    <div className="mt-1 mb-3 flex items-center justify-end opacity-0 transition duration-150 group-hover:opacity-100">
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
  collapsedMessageIds,
  statusItems = [],
  toolPlan = null,
  thinkingEnabled = false,
  thinkingTrace = "",
  thinkingTraceAvailable = false,
  thinkingTraceExpanded = false,
  onToggleThinkingTrace,
}: MessageListProps) {
  const activeThinkingMessageId = isStreaming
    ? [...items].reverse().find((item) => item.role === "assistant" && !item.content.trim())?.id
    : null;
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
        const showSources = !isEmptyAssistant && item.id !== activeStreamingAssistantId;
        const showStreamingStatus =
          isEmptyAssistant && item.id === activeStreamingAssistantId && statusItems.length > 0;
        const showToolPlan = item.id === activeStreamingAssistantId && toolPlan !== null;
        const showThinkingTrace =
          isAssistant &&
          thinkingEnabled &&
          thinkingTraceAvailable &&
          item.id === activeStreamingAssistantId &&
          !showStreamingStatus;
        const attachments = item.attachments ?? [];

        if (!isAssistant) {
          return (
            <article className="mb-4 flex justify-end last:mb-0" key={item.id}>
              <div className="group max-w-[420px]">
                <MessageImageStrip align="end" attachments={attachments} />
                {item.content.trim() ? (
                  <div className="rounded-[20px] bg-app-panel-soft px-4 py-2.5 text-left text-[15px] leading-7 text-app-accent-strong">
                    {renderMessageContent(item.content)}
                  </div>
                ) : null}
                <UserActions content={item.content} hidden={hideActions} />
              </div>
            </article>
          );
        }

        if (isEmptyAssistant && item.id !== activeThinkingMessageId && !showThinkingTrace) {
          return null;
        }

        return (
          <article className="mb-5 flex justify-start last:mb-0" key={item.id}>
            <div className="w-full max-w-[760px]">
              {showToolPlan ? <ToolPlanPanel plan={toolPlan} /> : null}

              {showThinkingTrace ? (
                <ThinkingPanel
                  expanded={thinkingTraceExpanded}
                  onToggle={() => onToggleThinkingTrace?.()}
                  trace={thinkingTrace}
                />
              ) : null}

              {showStreamingStatus ? <StreamingStatusList items={statusItems} /> : null}

              {!isEmptyAssistant ? (
                <div className="text-[15px] leading-8 text-app-text">
                  <MarkdownMessage content={item.content} />
                </div>
              ) : item.id === activeThinkingMessageId && !showThinkingTrace && !showStreamingStatus ? (
                <ActivityIndicator label="Thinking" />
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
