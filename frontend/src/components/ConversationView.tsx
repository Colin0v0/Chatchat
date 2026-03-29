import { useEffect, useLayoutEffect, useRef } from "react";

import type { ComposerAttachmentDraft } from "../app/useComposerAttachments";
import type { ConversationDetail, ModelOption, RetrievalMode } from "../types";
import { ChatComposer } from "./ChatComposer";
import { MessageList } from "./MessageList";

interface ConversationViewProps {
  conversation: ConversationDetail;
  collapsedMessageIds?: ReadonlySet<number | string>;
  draft: string;
  draftAttachments: ComposerAttachmentDraft[];
  attachmentUploadAvailable: boolean;
  isStreaming: boolean;
  model: string;
  models: ModelOption[];
  retrievalMode: RetrievalMode;
  submitBlocked: boolean;
  submitBlockedReason: string | null;
  thinkingEnabled: boolean;
  thinkingAvailable: boolean;
  streamingStatusLabel: string | null;
  thinkingTrace: string;
  thinkingTraceExpanded: boolean;
  onChangeDraft: (value: string) => void;
  onModelChange: (value: string) => void;
  onRemoveDraftAttachment: (attachmentId: string) => void;
  onRetry: (messageId: number | string) => void;
  onReuseUserMessage: (content: string) => void;
  onSelectAttachments: (files: FileList | File[]) => void;
  onSend: () => void;
  onStop: () => void;
  onToggleRag: () => void;
  onToggleWeb: () => void;
  onToggleThinking: () => void;
  onToggleThinkingTrace: () => void;
}

export function ConversationView({
  conversation,
  collapsedMessageIds,
  draft,
  draftAttachments,
  attachmentUploadAvailable,
  isStreaming,
  model,
  models,
  retrievalMode,
  submitBlocked,
  submitBlockedReason,
  thinkingEnabled,
  thinkingAvailable,
  streamingStatusLabel,
  thinkingTrace,
  thinkingTraceExpanded,
  onChangeDraft,
  onModelChange,
  onRemoveDraftAttachment,
  onRetry,
  onReuseUserMessage,
  onSelectAttachments,
  onSend,
  onStop,
  onToggleRag,
  onToggleWeb,
  onToggleThinking,
  onToggleThinkingTrace,
}: ConversationViewProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);
  const lastConversationIdRef = useRef<number | null>(null);

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

    const conversationChanged = lastConversationIdRef.current !== conversation.id;
    lastConversationIdRef.current = conversation.id;

    if (!conversationChanged && !stickToBottomRef.current) {
      return;
    }

    const activeContainer = scrollContainer;
    const frame = window.requestAnimationFrame(() => {
      activeContainer.scrollTop = activeContainer.scrollHeight;
      if (conversationChanged) {
        stickToBottomRef.current = true;
      }
    });

    return () => window.cancelAnimationFrame(frame);
  }, [
    conversation.id,
    conversation.messages,
    collapsedMessageIds,
    isStreaming,
    streamingStatusLabel,
    thinkingTrace,
    thinkingTraceExpanded,
  ]);

  return (
    <section className="flex min-h-0 flex-1 flex-col pb-1">
      <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto pt-4" ref={scrollRef}>
        <div className="px-4 md:px-6">
          <MessageList
            collapsedMessageIds={collapsedMessageIds}
            isStreaming={isStreaming}
            items={conversation.messages}
            onRetry={onRetry}
            onReuseUserMessage={onReuseUserMessage}
            onToggleThinkingTrace={onToggleThinkingTrace}
            streamingStatusLabel={streamingStatusLabel}
            thinkingTrace={thinkingTrace}
            thinkingTraceExpanded={thinkingTraceExpanded}
          />
        </div>
      </div>

      <div className="px-4 pt-2 md:px-6">
        <ChatComposer
          attachmentUploadAvailable={attachmentUploadAvailable}
          attachments={draftAttachments}
          isStreaming={isStreaming}
          model={model}
          models={models}
          onChange={onChangeDraft}
          onModelChange={onModelChange}
          onRemoveAttachment={onRemoveDraftAttachment}
          onSelectAttachments={onSelectAttachments}
          onStop={onStop}
          onSubmit={onSend}
          onToggleRag={onToggleRag}
          onToggleThinking={onToggleThinking}
          onToggleWeb={onToggleWeb}
          retrievalMode={retrievalMode}
          submitBlocked={submitBlocked}
          submitBlockedReason={submitBlockedReason}
          thinkingAvailable={thinkingAvailable}
          thinkingEnabled={thinkingEnabled}
          value={draft}
        />
      </div>
    </section>
  );
}
