import { useCallback, useEffect, useRef } from "react";

import type { ComposerAttachmentDraft } from "../model/useComposerAttachments";
import type {
  ConversationDetail,
  ComposerMode,
  FeedbackValue,
  MemoryCandidateUpdatePayload,
  ModelOption,
  ReasoningProfileValue,
  ToolMode,
} from "../../../types";
import { ChatComposer } from "./ChatComposer";
import { MessageList } from "./MessageList";

interface ConversationViewProps {
  canLoadEarlierMessages: boolean;
  conversation: ConversationDetail;
  collapsedMessageIds?: ReadonlySet<number | string>;
  draft: string;
  draftAttachments: ComposerAttachmentDraft[];
  editingUserMessageContent: string;
  editingUserMessageId: number | string | null;
  attachmentUploadAvailable: boolean;
  earlierMessagesError: string | null;
  isLoadingEarlierMessages: boolean;
  isRecording: boolean;
  isReasoningStreaming: boolean;
  isStreaming: boolean;
  isTranscribing: boolean;
  model: string;
  models: ModelOption[];
  composerMode: ComposerMode;
  reserveThinkingSpace: boolean;
  reasoningProfile: ReasoningProfileValue;
  toolMode: ToolMode;
  knowledgeFolders: string[];
  knowledgeFolder: string;
  submitBlocked: boolean;
  submitBlockedReason: string | null;
  streamingStatusLabel: string | null;
  onChangeDraft: (value: string) => void;
  onChangeEditingUserMessage: (value: string) => void;
  onModelChange: (value: string) => void;
  onComposerModeChange: (value: ComposerMode) => void;
  onReasoningProfileChange: (value: ReasoningProfileValue) => void;
  onKnowledgeFolderChange: (value: string) => void;
  onCancelEditingUserMessage: () => void;
  onLoadEarlierMessages: () => Promise<void> | void;
  onRemoveDraftAttachment: (attachmentId: string) => void;
  onConfirmPendingMemory: (memoryId: number, payload?: MemoryCandidateUpdatePayload) => Promise<void> | void;
  onFeedback: (messageId: number, value: FeedbackValue | null) => void;
  onRefreshMessagePendingMemories: (messageId: number) => Promise<void> | void;
  onRejectPendingMemory: (memoryId: number) => Promise<void> | void;
  onRetry: (messageId: number | string) => void;
  onStartEditingUserMessage: (messageId: number | string) => void;
  onSubmitEditingUserMessage: (messageId: number | string) => void;
  onSelectAttachments: (files: FileList | File[]) => void;
  onSend: () => void;
  onStop: () => void;
  onNewDebate: () => void;
  onNewBattle: () => void;
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
  editingUserMessageContent,
  editingUserMessageId,
  attachmentUploadAvailable,
  earlierMessagesError,
  isLoadingEarlierMessages,
  isRecording,
  isReasoningStreaming,
  isStreaming,
  isTranscribing,
  model,
  models,
  composerMode,
  reserveThinkingSpace,
  reasoningProfile,
  toolMode,
  knowledgeFolders,
  knowledgeFolder,
  submitBlocked,
  submitBlockedReason,
  streamingStatusLabel,
  onChangeDraft,
  onChangeEditingUserMessage,
  onModelChange,
  onComposerModeChange,
  onReasoningProfileChange,
  onKnowledgeFolderChange,
  onCancelEditingUserMessage,
  onLoadEarlierMessages,
  onRemoveDraftAttachment,
  onConfirmPendingMemory,
  onFeedback,
  onRefreshMessagePendingMemories,
  onRejectPendingMemory,
  onRetry,
  onStartEditingUserMessage,
  onSubmitEditingUserMessage,
  onSelectAttachments,
  onSend,
  onStop,
  onNewDebate,
  onNewBattle,
  onToggleRecording,
  onToggleRag,
  onToggleWeb,
}: ConversationViewProps) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const stickToBottomRef = useRef(true);
  const lastConversationIdRef = useRef<number | null>(null);
  const pendingScrollToBottomRef = useRef(false);
  const loadEarlierInFlightRef = useRef(false);
  const prependSnapshotRef = useRef<{ scrollHeight: number; scrollTop: number } | null>(null);

  const requestLoadEarlierMessages = useCallback(async () => {
    const scrollContainer = scrollRef.current;
    if (
      !scrollContainer
      || loadEarlierInFlightRef.current
      || isLoadingEarlierMessages
      || !canLoadEarlierMessages
    ) {
      return;
    }

    loadEarlierInFlightRef.current = true;
    prependSnapshotRef.current = {
      scrollHeight: scrollContainer.scrollHeight,
      scrollTop: scrollContainer.scrollTop,
    };

    try {
      await onLoadEarlierMessages();
    } finally {
      loadEarlierInFlightRef.current = false;
    }
  }, [canLoadEarlierMessages, isLoadingEarlierMessages, onLoadEarlierMessages]);

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

      if (
        lastConversationIdRef.current === conversation.id
        && activeContainer.scrollTop <= 120
        && canLoadEarlierMessages
        && !isLoadingEarlierMessages
        && !earlierMessagesError
      ) {
        void requestLoadEarlierMessages();
      }
    }

    handleScroll();
    activeContainer.addEventListener("scroll", handleScroll);
    return () => activeContainer.removeEventListener("scroll", handleScroll);
  }, [
    conversation.id,
    canLoadEarlierMessages,
    earlierMessagesError,
    isLoadingEarlierMessages,
    requestLoadEarlierMessages,
  ]);

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

    if (conversationChanged) {
      pendingScrollToBottomRef.current = true;
      stickToBottomRef.current = true;
    }

    if (!pendingScrollToBottomRef.current && !stickToBottomRef.current) {
      return;
    }

    const activeContainer = scrollContainer;
    const frame = window.requestAnimationFrame(() => {
      activeContainer.scrollTop = activeContainer.scrollHeight;
      pendingScrollToBottomRef.current = false;
    });

    return () => window.cancelAnimationFrame(frame);
  }, [
    conversation.id,
    conversation.messages,
    collapsedMessageIds,
    isStreaming,
    streamingStatusLabel,
  ]);

  useEffect(() => {
    const scrollContainer = scrollRef.current;
    if (
      !scrollContainer
      || !canLoadEarlierMessages
      || isLoadingEarlierMessages
      || earlierMessagesError
    ) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      if (scrollContainer.scrollHeight <= scrollContainer.clientHeight + 48) {
        void requestLoadEarlierMessages();
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [
    canLoadEarlierMessages,
    conversation.messages,
    earlierMessagesError,
    isLoadingEarlierMessages,
    requestLoadEarlierMessages,
  ]);

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden pb-1">
      <div className="relative min-h-0 flex-1 overflow-hidden">
        <div className="app-scrollbar h-full min-h-0 overflow-y-auto pt-4" ref={scrollRef}>
          <div className="mx-auto w-full max-w-[920px] px-4 md:px-6" data-pet-anchor="messageArea">
            {isLoadingEarlierMessages ? (
              <div className="mb-3 flex justify-center">
                <div className="inline-flex items-center rounded-full px-3 py-1 text-xs text-app-muted">
                  正在加载更早消息...
                </div>
              </div>
            ) : earlierMessagesError ? (
              <div className="mb-3 flex justify-center">
                <button
                  className="inline-flex min-h-8 items-center rounded-full border border-app-line px-3 text-xs text-app-muted transition hover:border-app-accent/35 hover:text-app-text"
                  onClick={() => void requestLoadEarlierMessages()}
                  type="button"
                >
                  加载更早消息失败，点击重试
                </button>
              </div>
            ) : null}
            <MessageList
              collapsedMessageIds={collapsedMessageIds}
              conversationModel={conversation.model}
              editingUserMessageContent={editingUserMessageContent}
              editingUserMessageId={editingUserMessageId}
              isReasoningStreaming={isReasoningStreaming}
              onFeedback={onFeedback}
              onConfirmPendingMemory={onConfirmPendingMemory}
              onCancelEditingUserMessage={onCancelEditingUserMessage}
              onChangeEditingUserMessage={onChangeEditingUserMessage}
              onRefreshMessagePendingMemories={onRefreshMessagePendingMemories}
              onRejectPendingMemory={onRejectPendingMemory}
              onStartEditingUserMessage={onStartEditingUserMessage}
              isStreaming={isStreaming}
              items={conversation.messages}
              models={models}
              onRetry={onRetry}
              onSubmitEditingUserMessage={onSubmitEditingUserMessage}
              reserveThinkingSpace={reserveThinkingSpace}
              streamingStatusLabel={streamingStatusLabel}
            />
          </div>
        </div>

      </div>

      <div className="mx-auto w-full max-w-[920px] shrink-0 px-4 pt-2 md:px-6">
        <ChatComposer
          attachmentUploadAvailable={attachmentUploadAvailable}
          attachments={draftAttachments}
          isRecording={isRecording}
          isStreaming={isStreaming}
          isTranscribing={isTranscribing}
          model={model}
          models={models}
          composerMode={composerMode}
          onChange={onChangeDraft}
          onComposerModeChange={onComposerModeChange}
          onModelChange={onModelChange}
          onReasoningProfileChange={onReasoningProfileChange}
          knowledgeFolders={knowledgeFolders}
          knowledgeFolder={knowledgeFolder}
          onKnowledgeFolderChange={onKnowledgeFolderChange}
          onRemoveAttachment={onRemoveDraftAttachment}
          onSelectAttachments={onSelectAttachments}
          onNewDebate={onNewDebate}
          onNewBattle={onNewBattle}
          onStop={onStop}
          onSubmit={onSend}
          onToggleRecording={onToggleRecording}
          onToggleRag={onToggleRag}
          onToggleWeb={onToggleWeb}
          reasoningProfile={reasoningProfile}
          toolMode={toolMode}
          submitBlocked={submitBlocked}
          submitBlockedReason={submitBlockedReason}
          value={draft}
        />
      </div>
    </section>
  );
}
