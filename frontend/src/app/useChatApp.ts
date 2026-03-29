import {
  startTransition,
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useComposerAttachments } from "./useComposerAttachments";
import { useConversationStreams } from "./useConversationStreams";
import {
  deleteConversation,
  fetchConversation,
  fetchConversations,
  fetchModels,
  regenerateChat,
  reindexRag,
  renameConversation,
  streamChat,
} from "../lib/api";
import type {
  ConversationDetail,
  ConversationSummary,
  ModelOption,
  RagReindexResult,
  RetrievalMode,
} from "../types";
import { pickLandingTitle } from "./constants";
import {
  appendRetryDraft,
  createAssistantDraftMessage,
  createTransientAttachments,
  createUserDraftMessage,
  labelForStage,
  restoreAttachmentFiles,
  stageForRetrievalMode,
} from "./chatSessionUtils";
import {
  createInitialModelOptions,
  createModelOption,
  ensureSelectedModel,
  findModelOption,
  resolveInitialSelectedModel,
} from "./modelOptions";

type UseChatAppOptions = {
  closeMobileSidebar: () => void;
  isDesktop: boolean;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
};

function toggleRetrievalMode(current: RetrievalMode, next: Exclude<RetrievalMode, "none">): RetrievalMode {
  return current === next ? "none" : next;
}

export function useChatApp({
  closeMobileSidebar,
  isDesktop,
  sidebarOpen,
  toggleSidebar,
}: UseChatAppOptions) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationsLoaded, setConversationsLoaded] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [activeConversation, setActiveConversation] = useState<ConversationDetail | null>(null);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [models, setModels] = useState<ModelOption[]>(() => createInitialModelOptions());
  const [selectedModel, setSelectedModel] = useState("openai:deepseek-reasoner");
  const [collapsedMessageIds, setCollapsedMessageIds] = useState<Set<number | string>>(new Set());
  const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>("none");
  const [thinkingExpanded, setThinkingExpanded] = useState(false);
  const [landingHeroAnimated, setLandingHeroAnimated] = useState(false);
  const [landingTitle] = useState(() => pickLandingTitle());
  const [error, setError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [isUpdatingRag, setIsUpdatingRag] = useState(false);
  const [ragUpdateError, setRagUpdateError] = useState<string | null>(null);
  const [ragUpdateResult, setRagUpdateResult] = useState<RagReindexResult | null>(null);
  const { addAttachments, clearAttachments, draftAttachments, removeAttachment, replaceAttachments } =
    useComposerAttachments();
  const transientAttachmentUrlsRef = useRef<string[]>([]);
  const deferredQuery = useDeferredValue(query);

  const selectedModelOption = useMemo(
    () => findModelOption(models, selectedModel),
    [models, selectedModel],
  );
  const thinkingAvailable = selectedModelOption.supports_thinking;
  const thinkingEnabled =
    thinkingAvailable && selectedModelOption.reasoning_model === selectedModel;
  const attachmentUploadAvailable = selectedModelOption.supports_attachment_upload;

  const clearTransientAttachmentUrls = useCallback(() => {
    transientAttachmentUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    transientAttachmentUrlsRef.current = [];
  }, []);

  const {
    abortAndRemoveSession,
    activeSession,
    conversationActivity,
    getSessionConversation,
    isStreaming,
    mergeConversationSummariesWithSessions,
    openSessionConversation,
    renameSession,
    runningSessions,
    runStream,
    stopStream,
    visibleStreaming,
  } = useConversationStreams({
    activeConversation,
    activeConversationId,
    setActiveConversation,
    setActiveConversationId,
    setConversations,
    setError,
    setSelectedModel,
    setThinkingExpanded,
  });
  const hasRunningOllamaSession = useMemo(
    () => runningSessions.some((session) => session.conversation.model.startsWith("ollama:")),
    [runningSessions],
  );
  const submitBlocked =
    !isStreaming && selectedModel.startsWith("ollama:") && hasRunningOllamaSession;
  const submitBlockedReason = submitBlocked
    ? "Ollama 同时只允许一个回答运行中，请先停止当前本地生成，避免内存占满。"
    : null;

  const loadConversation = useCallback(
    async (conversationId: number) => {
      const sessionConversation = getSessionConversation(conversationId);
      if (sessionConversation) {
        setActiveConversation(sessionConversation);
        setSelectedModel(sessionConversation.model);
        return;
      }

      const conversation = await fetchConversation(conversationId);
      setActiveConversation(conversation);
      setSelectedModel(conversation.model);
    },
    [getSessionConversation],
  );

  const filteredConversations = useMemo(() => {
    if (!deferredQuery.trim()) {
      return conversations;
    }

    const keyword = deferredQuery.toLowerCase();
    return conversations.filter(
      (item) =>
        item.title.toLowerCase().includes(keyword) ||
        item.last_message_preview.toLowerCase().includes(keyword),
    );
  }, [conversations, deferredQuery]);

  const availableModels = useMemo(
    () => ensureSelectedModel(models, selectedModel),
    [models, selectedModel],
  );

  const refreshConversations = useCallback(async () => {
    try {
      const items = await fetchConversations();
      setConversations(mergeConversationSummariesWithSessions(items));
    } finally {
      setConversationsLoaded(true);
    }
  }, [mergeConversationSummariesWithSessions]);

  const loadModels = useCallback(async () => {
    const payload = await fetchModels();
    const nextModels =
      payload.models.length > 0 ? payload.models : [createModelOption(payload.default_model)];
    setModels(nextModels);
    setSelectedModel(resolveInitialSelectedModel(nextModels, payload.default_model));
  }, []);

  useEffect(() => {
    void refreshConversations();
    void loadModels();
  }, [loadModels, refreshConversations]);

  useEffect(() => {
    if (activeConversationId === null) {
      return;
    }

    void loadConversation(activeConversationId);
  }, [activeConversationId, loadConversation]);

  useEffect(() => {
    return () => {
      clearTransientAttachmentUrls();
    };
  }, [clearTransientAttachmentUrls]);

  useEffect(() => {
    if (!error) {
      return;
    }

    const timeoutId = window.setTimeout(() => setError(null), 5000);
    return () => window.clearTimeout(timeoutId);
  }, [error]);

  const handleModelChange = useCallback((model: string) => {
    setSelectedModel(model);
  }, []);

  const handleToggleThinking = useCallback(() => {
    if (!thinkingAvailable) {
      return;
    }

    if (thinkingEnabled) {
      setSelectedModel(selectedModelOption.chat_model ?? selectedModel);
      return;
    }

    setSelectedModel(selectedModelOption.reasoning_model ?? selectedModel);
  }, [selectedModel, selectedModelOption, thinkingAvailable, thinkingEnabled]);

  const handleNewChat = useCallback(() => {
    clearAttachments();
    startTransition(() => {
      setActiveConversationId(null);
      setActiveConversation(null);
      setCollapsedMessageIds(new Set());
      setDraft("");
      setError(null);
      setThinkingExpanded(false);
      if (!isDesktop) {
        closeMobileSidebar();
      }
    });
  }, [clearAttachments, closeMobileSidebar, isDesktop]);

  const handleSelectConversation = useCallback(
    (conversationId: number) => {
      startTransition(() => {
        setActiveConversationId(conversationId);
        setError(null);
        setCollapsedMessageIds(new Set());
        setThinkingExpanded(false);
        openSessionConversation(conversationId);

        if (!isDesktop) {
          closeMobileSidebar();
        }
      });
    },
    [closeMobileSidebar, isDesktop, openSessionConversation],
  );

  const handleRenameConversation = useCallback(
    async (conversationId: number, title: string) => {
      await renameConversation(conversationId, title);
      setActiveConversation((current) =>
        current && current.id === conversationId ? { ...current, title } : current,
      );
      renameSession(conversationId, title);
      await refreshConversations();
    },
    [refreshConversations, renameSession],
  );

  const handleDeleteConversation = useCallback(
    async (conversationId: number) => {
      abortAndRemoveSession(conversationId);
      await deleteConversation(conversationId);
      await refreshConversations();

      if (activeConversationId === conversationId) {
        setActiveConversationId(null);
        setActiveConversation(null);
        setCollapsedMessageIds(new Set());
        setDraft("");
        clearAttachments();
      }
    },
    [abortAndRemoveSession, activeConversationId, clearAttachments, refreshConversations],
  );

  const handleUpdateRagDatabase = useCallback(async () => {
    if (isUpdatingRag) {
      return;
    }

    setRagUpdateError(null);
    setIsUpdatingRag(true);
    try {
      const result = await reindexRag();
      setRagUpdateResult(result);
    } catch (updateError) {
      setRagUpdateError(
        updateError instanceof Error ? updateError.message : "Update database failed.",
      );
    } finally {
      setIsUpdatingRag(false);
    }
  }, [isUpdatingRag]);

  const handleSend = useCallback(async () => {
    const message = draft.trim();
    const pendingFiles = draftAttachments.map((attachment) => attachment.file);
    if ((!message && pendingFiles.length === 0) || isStreaming) {
      return;
    }

    const effectiveModel = selectedModel;
    if (effectiveModel.startsWith("ollama:") && hasRunningOllamaSession) {
      setError("Ollama 同时只允许一个回答运行中，请先停止当前本地生成，避免内存占满。");
      return;
    }
    const tempConversationId =
      activeConversation?.id != null ? activeConversation.id : -Date.now();
    const initialStage =
      pendingFiles.length > 0 ? "analyzing_attachments" : stageForRetrievalMode(retrievalMode);
    const tempAttachments = createTransientAttachments(pendingFiles);
    transientAttachmentUrlsRef.current.push(...tempAttachments.map((item) => item.url));
    const tempUserMessageId = `user-${Date.now()}`;
    const tempUserMessage = createUserDraftMessage(tempUserMessageId, message, tempAttachments);
    const nextConversation: ConversationDetail = activeConversation
      ? {
          ...activeConversation,
          model: effectiveModel,
          messages: [...activeConversation.messages, tempUserMessage, createAssistantDraftMessage()],
        }
      : {
          id: tempConversationId,
          title: message.slice(0, 48) || "Attachment chat",
          model: effectiveModel,
          messages: [tempUserMessage, createAssistantDraftMessage()],
        };

    setDraft("");
    clearAttachments();
    setThinkingExpanded(false);
    setActiveConversationId(tempConversationId);
    setActiveConversation(nextConversation);

    const result = await runStream({
      conversation: nextConversation,
      errorMessage: "Failed to send message.",
      initialStage,
      restoreInput: {
        content: message,
        loadFiles: async () => pendingFiles,
      },
      tempUserMessageId,
      request: ({ onEvent, signal }) =>
        streamChat(
          {
            conversation_id:
              activeConversation && activeConversation.id > 0 ? activeConversation.id : null,
            message,
            files: pendingFiles,
            model: effectiveModel,
            retrieval_mode: retrievalMode,
          },
          { onEvent, signal },
        ),
    });

    if (result === "completed") {
      await refreshConversations();
    }
  }, [
    activeConversation,
    clearAttachments,
    draft,
    draftAttachments,
    hasRunningOllamaSession,
    isStreaming,
    refreshConversations,
    retrievalMode,
    runStream,
    selectedModel,
    setError,
  ]);

  const handleStop = useCallback(async () => {
    if (!activeConversation) {
      return;
    }

    await stopStream({
      conversationId: activeConversation.id,
      restoreAttachments: replaceAttachments,
      restoreDraft: setDraft,
    });
  }, [activeConversation, replaceAttachments, stopStream]);

  const handleRetryAssistant = useCallback(
    async (messageId: number | string) => {
      if (!activeConversation || isStreaming) {
        return;
      }

      const targetIndex = activeConversation.messages.findIndex((item) => item.id === messageId);
      if (targetIndex < 0) {
        return;
      }

      const sourceUser = [...activeConversation.messages.slice(0, targetIndex)]
        .reverse()
        .find((item) => item.role === "user");
      if (!sourceUser) {
        return;
      }

      const effectiveModel = selectedModel;
      if (effectiveModel.startsWith("ollama:") && hasRunningOllamaSession) {
        setError("Ollama 同时只允许一个回答运行中，请先停止当前本地生成，避免内存占满。");
        return;
      }
      const retryUserDraftId = `retry-user-${messageId}-${Date.now()}`;
      const nextConversation = appendRetryDraft(
        activeConversation,
        retryUserDraftId,
        sourceUser.content,
        sourceUser.attachments ?? [],
      );

      setCollapsedMessageIds((current) => new Set([...current, sourceUser.id, messageId]));
      setThinkingExpanded(false);
      setActiveConversation(nextConversation);

      const result = await runStream({
        conversation: nextConversation,
        errorMessage: "Failed to regenerate response.",
        initialStage: stageForRetrievalMode(retrievalMode),
        restoreInput: {
          content: sourceUser.content,
          loadFiles: () => restoreAttachmentFiles(sourceUser.attachments ?? []),
        },
        tempUserMessageId: retryUserDraftId,
        request: async ({ onEvent, signal }) => {
          if (typeof messageId === "number") {
            return regenerateChat(
              {
                conversation_id: activeConversation.id,
                assistant_message_id: messageId,
                model: effectiveModel,
                retrieval_mode: retrievalMode,
              },
              { onEvent, signal },
            );
          }

          const restoredFiles = await restoreAttachmentFiles(sourceUser.attachments ?? []);
          return streamChat(
            {
              conversation_id: activeConversation.id,
              message: sourceUser.content,
              files: restoredFiles,
              model: effectiveModel,
              retrieval_mode: retrievalMode,
            },
            { onEvent, signal },
          );
        },
      });

      if (result === "completed") {
        await refreshConversations();
      }
    },
    [
      activeConversation,
      hasRunningOllamaSession,
      isStreaming,
      refreshConversations,
      retrievalMode,
      runStream,
      selectedModel,
      setError,
    ],
  );

  const handleReuseUserMessage = useCallback((content: string) => {
    setDraft(content);
  }, []);

  const handleSelectRag = useCallback(() => {
    setRetrievalMode((current) => toggleRetrievalMode(current, "rag"));
  }, []);

  const handleSelectWeb = useCallback(() => {
    setRetrievalMode((current) => toggleRetrievalMode(current, "web"));
  }, []);

  const handleToggleThinkingTrace = useCallback(() => {
    setThinkingExpanded((current) => !current);
  }, []);

  const handleLandingAnimationComplete = useCallback(() => {
    setLandingHeroAnimated(true);
  }, []);

  const showLanding = !activeConversation || activeConversation.messages.length === 0;

  return {
    error,
    conversationProps: activeConversation
      ? {
          collapsedMessageIds,
          conversation: activeConversation,
          draft,
          draftAttachments,
          attachmentUploadAvailable,
          isStreaming: visibleStreaming,
          model: selectedModel,
          models: availableModels,
          onChangeDraft: setDraft,
          onModelChange: handleModelChange,
          onRemoveDraftAttachment: removeAttachment,
          onRetry: handleRetryAssistant,
          onReuseUserMessage: handleReuseUserMessage,
          onSelectAttachments: addAttachments,
          onSend: () => void handleSend(),
          onStop: handleStop,
          onToggleRag: handleSelectRag,
          onToggleThinking: handleToggleThinking,
          onToggleThinkingTrace: handleToggleThinkingTrace,
          onToggleWeb: handleSelectWeb,
          retrievalMode,
          submitBlocked,
          submitBlockedReason,
          streamingStatusLabel: visibleStreaming ? labelForStage(activeSession?.stage ?? null) : null,
          thinkingAvailable,
          thinkingEnabled,
          thinkingTrace: visibleStreaming ? activeSession?.reasoning ?? "" : "",
          thinkingTraceExpanded: thinkingExpanded,
        }
      : null,
    headerProps: {
      conversationId: activeConversationId,
      conversationTitle: activeConversation?.title ?? "",
      isDesktop,
      onDeleteConversation: handleDeleteConversation,
      onRenameConversation: handleRenameConversation,
      onToggleSidebar: toggleSidebar,
      showTitle: true,
      sidebarOpen,
      title: "Chatchat",
    },
    landingProps: {
      draft,
      draftAttachments,
      attachmentUploadAvailable,
      isStreaming,
      model: selectedModel,
      models: availableModels,
      onAnimationComplete: handleLandingAnimationComplete,
      onChangeDraft: setDraft,
      onModelChange: handleModelChange,
      onRemoveDraftAttachment: removeAttachment,
      onSelectAttachments: addAttachments,
      onSend: () => void handleSend(),
      onStop: handleStop,
      onToggleRag: handleSelectRag,
      onToggleThinking: handleToggleThinking,
      onToggleWeb: handleSelectWeb,
      retrievalMode,
      submitBlocked,
      submitBlockedReason,
      shouldAnimate: !landingHeroAnimated,
      thinkingAvailable,
      thinkingEnabled,
      title: landingTitle,
    },
    settingsProps: {
      isUpdating: isUpdatingRag,
      onClose: () => setSettingsOpen(false),
      onUpdateDatabase: () => void handleUpdateRagDatabase(),
      open: settingsOpen,
      updateError: ragUpdateError,
      updateResult: ragUpdateResult,
    },
    showLanding,
    sidebarProps: {
      activeConversationId,
      activity: conversationActivity,
      conversationsLoaded,
      isDesktop,
      items: filteredConversations,
      onDelete: handleDeleteConversation,
      onNewChat: handleNewChat,
      onOpenSettings: () => setSettingsOpen(true),
      onQueryChange: setQuery,
      onRename: handleRenameConversation,
      onSelect: handleSelectConversation,
      onToggleSidebar: toggleSidebar,
      open: sidebarOpen,
      query,
    },
  };
}
