import { Check, Copy, RotateCcw, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState, type ReactNode } from "react";

import { MarkdownMessage } from "./markdown/MarkdownMessage";
import { ThinkingPanel } from "./thinking/ThinkingPanel";
import type { ChatMessage } from "../types";

interface MessageListProps {
  items: ChatMessage[];
  isStreaming?: boolean;
  onRetry?: (messageId: number) => void;
  collapsedMessageIds?: ReadonlySet<number | string>;
  thinkingEnabled?: boolean;
  thinkingTrace?: string;
  thinkingTraceAvailable?: boolean;
  thinkingTraceExpanded?: boolean;
  onToggleThinkingTrace?: () => void;
}

function ThinkingIndicator() {
  return (
    <div className="inline-flex items-center gap-2.5 leading-none text-app-muted/80">
      <span className="animate-[thinking-dot_1.8s_ease-in-out_infinite] text-[15px] italic tracking-[0.01em]">
        Thinking
      </span>
      <div aria-hidden="true" className="inline-flex items-center gap-1.25 self-center">
        <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.15s_infinite]" />
        <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.3s_infinite]" />
        <span className="size-[4px] rounded-full bg-current animate-[thinking-dot_1.8s_ease-in-out_0.45s_infinite]" />
      </div>
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

  if (hidden) {
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
      {items.map((item, index) => {
        if (collapsedMessageIds?.has(item.id)) {
          const previousItem = index > 0 ? items[index - 1] : null;
          if (item.role === "assistant" && previousItem && collapsedMessageIds.has(previousItem.id)) {
            return (
              <div
                className="mb-3 text-[12px] font-medium tracking-[0.06em] text-app-muted/70"
                key={`collapsed-${item.id}`}
              >
                Previous attempt collapsed
              </div>
            );
          }
          return null;
        }

        const isAssistant = item.role === "assistant";
        const isEmptyAssistant = isAssistant && !item.content.trim();
        const showThinkingTrace =
          isAssistant &&
          thinkingEnabled &&
          thinkingTraceAvailable &&
          item.id === activeStreamingAssistantId &&
          (isStreaming || Boolean(thinkingTrace.trim()));

        if (!isAssistant) {
          return (
            <article className="flex justify-end" key={item.id}>
              <div className="group max-w-[420px]">
                <div className="rounded-[20px] bg-app-panel-soft px-4 py-2.5 text-right text-[15px] leading-7 text-app-accent-strong">
                  {renderMessageContent(item.content)}
                </div>
                <UserActions content={item.content} hidden={hideActions} />
              </div>
            </article>
          );
        }

        if (isEmptyAssistant && item.id !== activeThinkingMessageId && !showThinkingTrace) {
          return null;
        }

        return (
          <article className="flex justify-start" key={item.id}>
            <div className="w-full max-w-[760px]">
              {showThinkingTrace ? (
                <ThinkingPanel
                  expanded={thinkingTraceExpanded}
                  onToggle={() => onToggleThinkingTrace?.()}
                  trace={thinkingTrace}
                />
              ) : null}

              {!isEmptyAssistant ? (
                <div className="text-[15px] leading-8 text-app-text">
                  <MarkdownMessage content={item.content} />
                </div>
              ) : item.id === activeThinkingMessageId && !showThinkingTrace ? (
                <ThinkingIndicator />
              ) : null}

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