import { useEffect, useRef } from "react";

import type { ComposerAttachmentDraft } from "../app/useComposerAttachments";
import type { ConversationDetail, FeedbackValue, ModelOption, RetrievalMode } from "../types";
import { ChatComposer } from "./ChatComposer";
import { MessageList } from "./MessageList";

interface ConversationViewProps {
  canLoadEarlierMessages: boolean;
  conversation: ConversationDetail;
  collapsedMessageIds?: ReadonlySet<number | string>;
  draft: string;
  draftAttachments: ComposerAttachmentDraft[];
  attachmentUploadAvailable: boolean;
  isLoadingEarlierMessages: boolean;
  isRecording: boolean;
  isReasoningStreaming: boolean;
  isStreaming: boolean;
  isTranscribing: boolean;
  model: string;
  models: ModelOption[];
  retrievalMode: RetrievalMode;
  submitBlocked: boolean;
  submitBlockedReason: string | null;
  streamingStatusLabel: string | null;
  onChangeDraft: (value: string) => void;
  onModelChange: (value: string) => void;
  onLoadEarlierMessages: () => Promise<void> | void;
  onRemoveDraftAttachment: (attachmentId: string) => void;
  onFeedback: (messageId: number, value: FeedbackValue | null) => void;
  onRetry: (messageId: number | string) => void;
  onReuseUserMessage: (content: string) => void;
  onSelectAttachments: (files: FileList | File[]) => void;
  onSend: () => void;
  onStop: () => void;
  onToggleRecording: () => void;
  onToggleRag: () => void;
  onToggleWeb: () => void;
}

export function ConversationView({
  canLoadEarlierMessages,
  conversation,
  collapsedMessageIds,
  draft,
  draftAttachments,
  attachmentUploadAvailable,
  isLoadingEarlierMessages,
  isRecording,
  isReasoningStreaming,
  isStreaming,
  isTranscribing,
  model,
  models,
  retrievalMode,
  submitBlocked,
  submitBlockedReason,
  streamingStatusLabel,
  onChangeDraft,
  onModelChange,
  onLoadEarlierMessages,
  onRemoveDraftAttachment,
  onFeedback,
  onRetry,
  onReuseUserMessage,
  onSelectAttachments,
  onSend,
  onStop,
  onToggleRecording,
  onToggleRag,
  onToggleWeb,
}: ConversationViewProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);
  const lastConversationIdRef = useRef<number | null>(null);
  const prependSnapshotRef = useRef<{ scrollHeight: number; scrollTop: number } | null>(null);

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

  useEffect(() => {
    const scrollContainer = scrollRef.current;
    if (!scrollContainer) {
      return;
    }

    if (prependSnapshotRef.current) {
      const snapshot = prependSnapshotRef.current;
      prependSnapshotRef.current = null;
      const frame = window.requestAnimationFrame(() => {
        scrollContainer.scrollTop = snapshot.scrollTop + (scrollContainer.scrollHeight - snapshot.scrollHeight);
      });
      return () => window.cancelAnimationFrame(frame);
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
  ]);

  async function handleLoadEarlierClick() {
    const scrollContainer = scrollRef.current;
    if (!scrollContainer || isLoadingEarlierMessages) {
      return;
    }

    prependSnapshotRef.current = {
      scrollHeight: scrollContainer.scrollHeight,
      scrollTop: scrollContainer.scrollTop,
    };
    await onLoadEarlierMessages();
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col pb-1">
      <div className="app-scrollbar min-h-0 flex-1 overflow-y-auto pt-4" ref={scrollRef}>
        <div className="mx-auto w-full max-w-[920px] px-4 md:px-6">
          {canLoadEarlierMessages ? (
            <div className="mb-4 flex justify-center">
              <button
                className="inline-flex min-h-9 items-center rounded-full border border-app-line px-4 text-sm text-app-muted transition hover:border-app-accent/35 hover:text-app-text disabled:cursor-wait disabled:opacity-60"
                disabled={isLoadingEarlierMessages}
                onClick={() => void handleLoadEarlierClick()}
                type="button"
              >
                {isLoadingEarlierMessages ? "Loading..." : `Load earlier messages (${conversation.remaining_message_count})`}
              </button>
            </div>
          ) : null}
          <MessageList
            collapsedMessageIds={collapsedMessageIds}
            isReasoningStreaming={isReasoningStreaming}
            onFeedback={onFeedback}
            isStreaming={isStreaming}
            items={conversation.messages}
            onRetry={onRetry}
            onReuseUserMessage={onReuseUserMessage}
            streamingStatusLabel={streamingStatusLabel}
          />
        </div>
      </div>

      <div className="mx-auto w-full max-w-[920px] pl-4 pr-4 pt-2 md:pl-6 md:pr-[34px]">
        <ChatComposer
          attachmentUploadAvailable={attachmentUploadAvailable}
          attachments={draftAttachments}
          isRecording={isRecording}
          isStreaming={isStreaming}
          isTranscribing={isTranscribing}
          model={model}
          models={models}
          onChange={onChangeDraft}
          onModelChange={onModelChange}
          onRemoveAttachment={onRemoveDraftAttachment}
          onSelectAttachments={onSelectAttachments}
          onStop={onStop}
          onSubmit={onSend}
          onToggleRecording={onToggleRecording}
          onToggleRag={onToggleRag}
          onToggleWeb={onToggleWeb}
          retrievalMode={retrievalMode}
          submitBlocked={submitBlocked}
          submitBlockedReason={submitBlockedReason}
          value={draft}
        />
      </div>
    </section>
  );
}
