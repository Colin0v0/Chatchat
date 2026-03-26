import { useEffect, useLayoutEffect, useRef } from "react";

import { ChatComposer } from "./ChatComposer";
import { MessageList } from "./MessageList";
import type { ConversationDetail, ModelOption } from "../types";

interface ConversationViewProps {
  conversation: ConversationDetail;
  collapsedMessageIds?: ReadonlySet<number | string>;
  draft: string;
  isStreaming: boolean;
  model: string;
  models: ModelOption[];
  ragEnabled: boolean;
  thinkingEnabled: boolean;
  thinkingAvailable: boolean;
  thinkingTrace: string;
  thinkingTraceAvailable: boolean;
  thinkingTraceExpanded: boolean;
  onChangeDraft: (value: string) => void;
  onModelChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  onRetry: (messageId: number) => void;
  onToggleRag: () => void;
  onToggleThinking: () => void;
  onToggleThinkingTrace: () => void;
}

export function ConversationView({
  conversation,
  collapsedMessageIds,
  draft,
  isStreaming,
  model,
  models,
  ragEnabled,
  thinkingEnabled,
  thinkingAvailable,
  thinkingTrace,
  thinkingTraceAvailable,
  thinkingTraceExpanded,
  onChangeDraft,
  onModelChange,
  onSend,
  onStop,
  onRetry,
  onToggleRag,
  onToggleThinking,
  onToggleThinkingTrace,
}: ConversationViewProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);

  useEffect(() => {
    const scrollContainer = scrollRef.current;
    if (!scrollContainer) {
      return;
    }

    const activeContainer = scrollContainer;

    function handleScroll() {
      const distanceToBottom =
        activeContainer.scrollHeight - activeContainer.scrollTop - activeContainer.clientHeight;
      stickToBottomRef.current = distanceToBottom <= 48;
    }

    handleScroll();
    activeContainer.addEventListener("scroll", handleScroll);
    return () => activeContainer.removeEventListener("scroll", handleScroll);
  }, []);

  useLayoutEffect(() => {
    const scrollContainer = scrollRef.current;
    if (!scrollContainer) {
      return;
    }

    if (!isStreaming && !thinkingTraceExpanded && !stickToBottomRef.current) {
      return;
    }

    const activeContainer = scrollContainer;
    const frame = window.requestAnimationFrame(() => {
      activeContainer.scrollTop = activeContainer.scrollHeight;
      stickToBottomRef.current = true;
    });

    return () => window.cancelAnimationFrame(frame);
  }, [conversation.messages, collapsedMessageIds, isStreaming, thinkingTrace, thinkingTraceExpanded]);

  return (
    <section className="flex min-h-0 flex-1 flex-col pb-1">
      <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto pt-4" ref={scrollRef}>
        <div className="px-4 md:px-6">
          <MessageList
            collapsedMessageIds={collapsedMessageIds}
            isStreaming={isStreaming}
            items={conversation.messages}
            onRetry={onRetry}
            onToggleThinkingTrace={onToggleThinkingTrace}
            thinkingEnabled={thinkingEnabled}
            thinkingTrace={thinkingTrace}
            thinkingTraceAvailable={thinkingTraceAvailable}
            thinkingTraceExpanded={thinkingTraceExpanded}
          />
        </div>
      </div>

      <div className="px-4 pt-2 md:px-6">
        <ChatComposer
          isStreaming={isStreaming}
          model={model}
          models={models}
          onChange={onChangeDraft}
          onModelChange={onModelChange}
          onStop={onStop}
          onSubmit={onSend}
          onToggleRag={onToggleRag}
          onToggleThinking={onToggleThinking}
          ragEnabled={ragEnabled}
          thinkingAvailable={thinkingAvailable}
          thinkingEnabled={thinkingEnabled}
          value={draft}
        />
      </div>
    </section>
  );
}