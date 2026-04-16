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
import { useLatestRequestGuard } from "./useLatestRequestGuard";
import {
  createDebateSession,
  deleteDebateSession,
  deleteConversation,
  fetchDebateSession,
  fetchDebateSessions,
  fetchConversation,
  fetchConversationMessages,
  fetchConversations,
  fetchModels,
  regenerateChat,
  renameDebateSession,
  renameConversation,
  streamChat,
  transcribeAudio,
  updateMessageFeedback,
} from "../lib/api";
import type {
  ConversationDetail,
  ConversationSummary,
  DebateSessionDetail,
  DebateSessionSummary,
  ModelOption,
  RetrievalMode,
} from "../types";
import { deriveConversationTitle, INITIAL_CHAT_MODEL, pickLandingTitle } from "./constants";
import { useAudioRecorder } from "./useAudioRecorder";
import { useKnowledgeManager } from "./useKnowledgeManager";
import {
  appendRetryDraft,
  createAssistantDraftMessage,
  createTransientAttachments,
  createUserDraftMessage,
  labelForStage,
  restoreAttachmentFiles,
  stageForRetrievalMode,
} from "./chatSessionUtils";
import { useMemoryManager } from "./useMemoryManager";
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

const CONVERSATION_VIEW_MESSAGE_LIMIT = 10;

function toggleRetrievalMode(current: RetrievalMode, next: Exclude<RetrievalMode, "none">): RetrievalMode {
  return current === next ? "none" : next;
}

function mergeDraftWithTranscript(current: string, transcript: string): string {
  const normalizedTranscript = transcript.trim();
  if (!normalizedTranscript) {
    return current;
  }

  if (!current.trim()) {
    return normalizedTranscript;
  }

  const suffix = current.endsWith("\n") ? "" : "\n";
  return `${current}${suffix}${normalizedTranscript}`;
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
  const [debateSessions, setDebateSessions] = useState<DebateSessionSummary[]>([]);
  const [debateSessionsLoaded, setDebateSessionsLoaded] = useState(false);
  const [activeDebateId, setActiveDebateId] = useState<number | null>(null);
  const [activeDebate, setActiveDebate] = useState<DebateSessionDetail | null>(null);
  const [debateCreateOpen, setDebateCreateOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [models, setModels] = useState<ModelOption[]>(() => createInitialModelOptions());
  const [selectedModel, setSelectedModel] = useState(INITIAL_CHAT_MODEL);
  const [collapsedMessageIds, setCollapsedMessageIds] = useState<Set<number | string>>(new Set());
  const [retrievalMode, setRetrievalMode] = useState<RetrievalMode>("none");
  const [landingHeroAnimated, setLandingHeroAnimated] = useState(false);
  const [landingTitle] = useState(() => pickLandingTitle());
  const [error, setError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isLoadingEarlierMessages, setIsLoadingEarlierMessages] = useState(false);
  const memoryManager = useMemoryManager({
    activeConversationId: activeConversationId && activeConversationId > 0 ? activeConversationId : null,
    open: settingsOpen,
  });
  const knowledgeManager = useKnowledgeManager({ open: settingsOpen });
  const { addAttachments, clearAttachments, draftAttachments, removeAttachment, replaceAttachments } =
    useComposerAttachments();
  const { cancelRecording, isRecording, recordingError, startRecording, stopRecording } =
    useAudioRecorder();
  const transientAttachmentUrlsRef = useRef<string[]>([]);
  const conversationLoadAbortRef = useRef<AbortController | null>(null);
  const earlierMessagesAbortRef = useRef<AbortController | null>(null);
  const debateLoadAbortRef = useRef<AbortController | null>(null);
  const conversationLoadGuard = useLatestRequestGuard();
  const conversationsRefreshGuard = useLatestRequestGuard();
  const debatesRefreshGuard = useLatestRequestGuard();
  const debateLoadGuard = useLatestRequestGuard();
  const modelsLoadGuard = useLatestRequestGuard();
  const deferredQuery = useDeferredValue(query);

  const selectedModelOption = useMemo(
    () => findModelOption(models, selectedModel),
    [models, selectedModel],
  );
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
  });
  const submitBlocked = false;
  const submitBlockedReason = null;

  const loadConversation = useCallback(
    async (conversationId: number) => {
      const requestId = conversationLoadGuard.begin();
      conversationLoadAbortRef.current?.abort();
      const sessionConversation = getSessionConversation(conversationId);
      if (sessionConversation) {
        setActiveConversation(sessionConversation);
        setSelectedModel(sessionConversation.model);
        return;
      }

      const controller = new AbortController();
      conversationLoadAbortRef.current = controller;

      try {
        const conversation = await fetchConversation(conversationId, {
          limit: CONVERSATION_VIEW_MESSAGE_LIMIT,
          signal: controller.signal,
        });
        if (!conversationLoadGuard.isCurrent(requestId)) {
          return;
        }
        setActiveConversation(conversation);
        setSelectedModel(conversation.model);
      } catch (loadError) {
        if (controller.signal.aborted) {
          return;
        }
        if (!conversationLoadGuard.isCurrent(requestId)) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Failed to load conversation.");
      } finally {
        if (conversationLoadAbortRef.current === controller) {
          conversationLoadAbortRef.current = null;
        }
      }
    },
    [conversationLoadGuard, getSessionConversation, setError],
  );

  const loadDebateSession = useCallback(
    async (sessionId: number) => {
      const requestId = debateLoadGuard.begin();
      debateLoadAbortRef.current?.abort();

      const controller = new AbortController();
      debateLoadAbortRef.current = controller;

      try {
        const session = await fetchDebateSession(sessionId);
        if (!debateLoadGuard.isCurrent(requestId)) {
          return;
        }
        setActiveDebate(session);
      } catch (loadError) {
        if (controller.signal.aborted) {
          return;
        }
        if (!debateLoadGuard.isCurrent(requestId)) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Failed to load debate session.");
      } finally {
        if (debateLoadAbortRef.current === controller) {
          debateLoadAbortRef.current = null;
        }
      }
    },
    [debateLoadGuard, setError],
  );

  const filteredConversations = useMemo(() => {
    if (!deferredQuery.trim()) {
      return conversations;
    }

    const keyword = deferredQuery.toLowerCase();
    return conversations.filter((item) => item.title.toLowerCase().includes(keyword));
  }, [conversations, deferredQuery]);

  const filteredDebateSessions = useMemo(() => {
    if (!deferredQuery.trim()) {
      return debateSessions;
    }

    const keyword = deferredQuery.toLowerCase();
    return debateSessions.filter((item) => item.topic.toLowerCase().includes(keyword));
  }, [debateSessions, deferredQuery]);

  const availableModels = useMemo(
    () => ensureSelectedModel(models, selectedModel),
    [models, selectedModel],
  );

  const refreshConversations = useCallback(async () => {
    const requestId = conversationsRefreshGuard.begin();
    try {
      const items = await fetchConversations();
      if (!conversationsRefreshGuard.isCurrent(requestId)) {
        return;
      }
      setConversations(mergeConversationSummariesWithSessions(items));
    } catch (refreshError) {
      if (conversationsRefreshGuard.isCurrent(requestId)) {
        setError(refreshError instanceof Error ? refreshError.message : "Failed to refresh conversations.");
      }
    } finally {
      if (conversationsRefreshGuard.isCurrent(requestId)) {
        setConversationsLoaded(true);
      }
    }
  }, [conversationsRefreshGuard, mergeConversationSummariesWithSessions, setError]);

  const refreshDebateSessions = useCallback(async () => {
    const requestId = debatesRefreshGuard.begin();
    try {
      const items = await fetchDebateSessions();
      if (!debatesRefreshGuard.isCurrent(requestId)) {
        return;
      }
      setDebateSessions(items);
    } catch (refreshError) {
      if (debatesRefreshGuard.isCurrent(requestId)) {
        setError(refreshError instanceof Error ? refreshError.message : "Failed to refresh debates.");
      }
    } finally {
      if (debatesRefreshGuard.isCurrent(requestId)) {
        setDebateSessionsLoaded(true);
      }
    }
  }, [debatesRefreshGuard, setError]);

  const loadModels = useCallback(async () => {
    const requestId = modelsLoadGuard.begin();
    try {
      const payload = await fetchModels();
      if (!modelsLoadGuard.isCurrent(requestId)) {
        return;
      }
      const nextModels =
        payload.models.length > 0 ? payload.models : [createModelOption(payload.default_model)];
      setModels(nextModels);
      setSelectedModel(resolveInitialSelectedModel(nextModels, payload.default_model));
    } catch (loadError) {
      if (modelsLoadGuard.isCurrent(requestId)) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load models.");
      }
    }
  }, [modelsLoadGuard, setError]);

  useEffect(() => {
    void refreshConversations();
    void refreshDebateSessions();
    void loadModels();
  }, [loadModels, refreshConversations, refreshDebateSessions]);

  useEffect(() => {
    if (activeConversationId === null) {
      return;
    }

    void loadConversation(activeConversationId);
  }, [activeConversationId, loadConversation]);

  useEffect(() => {
    if (activeDebateId === null) {
      return;
    }

    void loadDebateSession(activeDebateId);
  }, [activeDebateId, loadDebateSession]);

  useEffect(() => {
    return () => {
      conversationLoadAbortRef.current?.abort();
      earlierMessagesAbortRef.current?.abort();
      debateLoadAbortRef.current?.abort();
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

  useEffect(() => {
    if (!recordingError) {
      return;
    }
    setError(recordingError);
  }, [recordingError]);

  const handleModelChange = useCallback((model: string) => {
    setSelectedModel(model);
  }, []);

  const handleStartRecording = useCallback(async () => {
    if (isStreaming || isTranscribing) {
      return;
    }

    try {
      await startRecording();
    } catch (recordingStartError) {
      setError(
        recordingStartError instanceof Error
          ? recordingStartError.message
          : "Failed to start audio recording.",
      );
    }
  }, [isStreaming, isTranscribing, setError, startRecording]);

  const handleStopRecording = useCallback(async () => {
    if (!isRecording || isTranscribing) {
      return;
    }

    setIsTranscribing(true);
    try {
      const capture = await stopRecording();
      if (!capture.audioBlob) {
        setError("未捕获到有效音频，请检查 Edge 麦克风权限后重试。");
        return;
      }

      const result = await transcribeAudio(capture.audioBlob);
      if (!result.text.trim()) {
        return;
      }
      setDraft((current) => mergeDraftWithTranscript(current, result.text));
    } catch (transcriptionError) {
      setError(
        transcriptionError instanceof Error
          ? transcriptionError.message
          : "Failed to transcribe audio.",
      );
    } finally {
      setIsTranscribing(false);
    }
  }, [isRecording, isTranscribing, setError, stopRecording]);

  const handleToggleRecording = useCallback(() => {
    if (isRecording) {
      void handleStopRecording();
      return;
    }
    void handleStartRecording();
  }, [handleStartRecording, handleStopRecording, isRecording]);

  const handleNewChat = useCallback(() => {
    cancelRecording();
    conversationLoadAbortRef.current?.abort();
    earlierMessagesAbortRef.current?.abort();
    debateLoadAbortRef.current?.abort();
    clearAttachments();
    startTransition(() => {
      setActiveConversationId(null);
      setActiveConversation(null);
      setActiveDebateId(null);
      setActiveDebate(null);
      setDebateCreateOpen(false);
      setCollapsedMessageIds(new Set());
      setDraft("");
      setError(null);
      if (!isDesktop) {
        closeMobileSidebar();
      }
    });
  }, [cancelRecording, clearAttachments, closeMobileSidebar, isDesktop]);

  const handleSelectConversation = useCallback(
    (conversationId: number) => {
      cancelRecording();
      earlierMessagesAbortRef.current?.abort();
      debateLoadAbortRef.current?.abort();
      startTransition(() => {
        setActiveConversationId(conversationId);
        setActiveDebateId(null);
        setActiveDebate(null);
        setDebateCreateOpen(false);
        setError(null);
        setCollapsedMessageIds(new Set());
        openSessionConversation(conversationId);

        if (!isDesktop) {
          closeMobileSidebar();
        }
      });
    },
    [cancelRecording, closeMobileSidebar, isDesktop, openSessionConversation],
  );

  const handleNewDebate = useCallback(() => {
    cancelRecording();
    conversationLoadAbortRef.current?.abort();
    earlierMessagesAbortRef.current?.abort();
    debateLoadAbortRef.current?.abort();
    clearAttachments();
    startTransition(() => {
      setActiveConversationId(null);
      setActiveConversation(null);
      setActiveDebateId(null);
      setActiveDebate(null);
      setDebateCreateOpen(true);
      setCollapsedMessageIds(new Set());
      setDraft("");
      setError(null);
      if (!isDesktop) {
        closeMobileSidebar();
      }
    });
  }, [cancelRecording, clearAttachments, closeMobileSidebar, isDesktop]);

  const handleSelectDebate = useCallback(
    (sessionId: number) => {
      cancelRecording();
      earlierMessagesAbortRef.current?.abort();
      conversationLoadAbortRef.current?.abort();
      startTransition(() => {
        setActiveConversationId(null);
        setActiveConversation(null);
        setActiveDebateId(sessionId);
        setActiveDebate(null);
        setDebateCreateOpen(false);
        setError(null);
        setCollapsedMessageIds(new Set());

        if (!isDesktop) {
          closeMobileSidebar();
        }
      });
    },
    [cancelRecording, closeMobileSidebar, isDesktop],
  );

  const handleCreateDebate = useCallback(
    async (payload: { topic: string; proModelId: string; conModelId: string }) => {
      try {
        const created = await createDebateSession({
          topic: payload.topic,
          pro_model_id: payload.proModelId,
          con_model_id: payload.conModelId,
          retrieval_mode: "none",
          word_limit_level: "standard",
          style: "",
        });
        setDebateCreateOpen(false);
        setActiveDebateId(created.id);
        setActiveDebate(created);
        void refreshDebateSessions();
        if (!isDesktop) {
          closeMobileSidebar();
        }
      } catch (createError) {
        setError(createError instanceof Error ? createError.message : "Failed to create debate.");
      }
    },
    [closeMobileSidebar, isDesktop, refreshDebateSessions],
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
      cancelRecording();
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
    [abortAndRemoveSession, activeConversationId, cancelRecording, clearAttachments, refreshConversations],
  );

  const handleRenameDebate = useCallback(
    async (sessionId: number, topic: string) => {
      await renameDebateSession(sessionId, topic);
      setActiveDebate((current) =>
        current && current.id === sessionId ? { ...current, topic } : current,
      );
      await refreshDebateSessions();
    },
    [refreshDebateSessions],
  );

  const handleDeleteDebate = useCallback(
    async (sessionId: number) => {
      await deleteDebateSession(sessionId);
      await refreshDebateSessions();

      if (activeDebateId === sessionId) {
        setActiveDebateId(null);
        setActiveDebate(null);
      }
    },
    [activeDebateId, refreshDebateSessions],
  );

  const handleRefreshDebate = useCallback(
    async (sessionId: number) => {
      const refreshed = await fetchDebateSession(sessionId);
      setActiveDebate((current) => (current && current.id === sessionId ? refreshed : current));
      await refreshDebateSessions();
      return refreshed;
    },
    [refreshDebateSessions],
  );

  const handleSyncDebate = useCallback(
    (session: DebateSessionDetail) => {
      setActiveDebate((current) => (current && current.id === session.id ? session : current));
      void refreshDebateSessions();
    },
    [refreshDebateSessions],
  );

  const handleLoadEarlierMessages = useCallback(async () => {
    if (!activeConversation || activeConversation.id <= 0 || isLoadingEarlierMessages) {
      return;
    }

    const firstPersistedMessage = activeConversation.messages.find(
      (message) => typeof message.id === "number",
    );
    if (
      !firstPersistedMessage ||
      typeof firstPersistedMessage.id !== "number" ||
      activeConversation.remaining_message_count <= 0
    ) {
      return;
    }

    earlierMessagesAbortRef.current?.abort();
    const controller = new AbortController();
    earlierMessagesAbortRef.current = controller;
    setIsLoadingEarlierMessages(true);

    try {
      const page = await fetchConversationMessages(activeConversation.id, {
        beforeMessageId: firstPersistedMessage.id,
        limit: CONVERSATION_VIEW_MESSAGE_LIMIT,
        signal: controller.signal,
      });
      if (controller.signal.aborted) {
        return;
      }

      setActiveConversation((current) => {
        if (!current || current.id !== activeConversation.id) {
          return current;
        }
        const currentFirstPersistedMessage = current.messages.find(
          (message) => typeof message.id === "number",
        );
        if (currentFirstPersistedMessage?.id !== firstPersistedMessage.id) {
          return current;
        }

        return {
          ...current,
          messages: [...page.messages, ...current.messages],
          loaded_message_count: current.loaded_message_count + page.loaded_message_count,
          remaining_message_count: page.remaining_message_count,
        };
      });
    } catch (loadError) {
      if (controller.signal.aborted) {
        return;
      }
      setError(loadError instanceof Error ? loadError.message : "Failed to load earlier messages.");
    } finally {
      if (earlierMessagesAbortRef.current === controller) {
        earlierMessagesAbortRef.current = null;
      }
      setIsLoadingEarlierMessages(false);
    }
  }, [activeConversation, isLoadingEarlierMessages, setError]);

  const handleSend = useCallback(async () => {
    const message = draft.trim();
    const pendingFiles = draftAttachments.map((attachment) => attachment.file);
    if ((!message && pendingFiles.length === 0) || isRecording || isStreaming || isTranscribing) {
      return;
    }

    const effectiveModel = selectedModel;
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
          total_message_count: activeConversation.total_message_count + 2,
          loaded_message_count: activeConversation.loaded_message_count + 2,
          messages: [...activeConversation.messages, tempUserMessage, createAssistantDraftMessage()],
        }
      : {
          id: tempConversationId,
          title: deriveConversationTitle(message, tempAttachments.length),
          model: effectiveModel,
          total_message_count: 2,
          loaded_message_count: 2,
          remaining_message_count: 0,
          messages: [tempUserMessage, createAssistantDraftMessage()],
        };

    setDraft("");
    clearAttachments();
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
    isRecording,
    isStreaming,
    isTranscribing,
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
      const retryUserDraftId = `retry-user-${messageId}-${Date.now()}`;
      const nextConversation = appendRetryDraft(
        activeConversation,
        retryUserDraftId,
        sourceUser.content,
        sourceUser.attachments ?? [],
      );
      const retryConversation: ConversationDetail = {
        ...nextConversation,
        total_message_count: nextConversation.total_message_count + 2,
        loaded_message_count: nextConversation.loaded_message_count + 2,
      };

      setCollapsedMessageIds((current) => new Set([...current, sourceUser.id, messageId]));
      setActiveConversation(retryConversation);

      const result = await runStream({
        conversation: retryConversation,
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

  const handleMessageFeedback = useCallback(async (messageId: number, value: "up" | "down" | null) => {
    try {
      await updateMessageFeedback(messageId, value);
      setActiveConversation((current) =>
        current
          ? {
              ...current,
              messages: current.messages.map((message) =>
                message.id === messageId ? { ...message, feedback: value } : message,
              ),
            }
          : current,
      );
    } catch (feedbackError) {
      setError(feedbackError instanceof Error ? feedbackError.message : "Failed to save feedback.");
    }
  }, [setError]);

  const handleSelectRag = useCallback(() => {
    setRetrievalMode((current) => toggleRetrievalMode(current, "rag"));
  }, []);

  const handleSelectWeb = useCallback(() => {
    setRetrievalMode((current) => toggleRetrievalMode(current, "web"));
  }, []);

  const handleLandingAnimationComplete = useCallback(() => {
    setLandingHeroAnimated(true);
  }, []);

  const showLanding =
    !debateCreateOpen &&
    activeDebateId === null &&
    (!activeConversation || activeConversation.messages.length === 0);

  return {
    error,
    debateCreateProps: debateCreateOpen
      ? {
          defaultProModelId: selectedModel,
          defaultConModelId: selectedModel,
          models: availableModels,
          onCancel: () => setDebateCreateOpen(false),
          onCreate: handleCreateDebate,
        }
      : null,
    debateRoomProps: activeDebate
      ? {
          session: activeDebate,
          onRefresh: handleRefreshDebate,
          onSessionChange: handleSyncDebate,
        }
      : null,
    conversationProps: activeConversation
      ? {
          canLoadEarlierMessages: activeConversation.remaining_message_count > 0,
          collapsedMessageIds,
          conversation: activeConversation,
          draft,
          draftAttachments,
          attachmentUploadAvailable,
          isLoadingEarlierMessages,
          isRecording,
          isReasoningStreaming: activeSession?.reasoningStreaming ?? false,
          isStreaming: visibleStreaming,
          isTranscribing,
          model: selectedModel,
          models: availableModels,
          onChangeDraft: setDraft,
          onFeedback: (messageId: number, value: "up" | "down" | null) =>
            void handleMessageFeedback(messageId, value),
          onLoadEarlierMessages: () => void handleLoadEarlierMessages(),
          onModelChange: handleModelChange,
          onRemoveDraftAttachment: removeAttachment,
          onRetry: handleRetryAssistant,
          onReuseUserMessage: handleReuseUserMessage,
          onSelectAttachments: addAttachments,
          onSend: () => void handleSend(),
          onStop: handleStop,
          onToggleRecording: handleToggleRecording,
          onToggleRag: handleSelectRag,
          onToggleWeb: handleSelectWeb,
          retrievalMode,
          submitBlocked,
          submitBlockedReason,
          streamingStatusLabel: visibleStreaming ? labelForStage(activeSession?.stage ?? null) : null,
        }
      : null,
    headerProps: {
      activeItemId: activeDebateId ?? activeConversationId,
      activeItemKind:
        activeDebateId !== null ? ("debate" as const) : activeConversationId !== null ? ("chat" as const) : null,
      activeItemTitle: activeDebate?.topic ?? activeConversation?.title ?? "",
      isDesktop,
      onNewChat: handleNewChat,
      onNewDebate: handleNewDebate,
      onDeleteItem: async (itemId: number, kind: "chat" | "debate") => {
        if (kind === "debate") {
          await handleDeleteDebate(itemId);
          return;
        }
        await handleDeleteConversation(itemId);
      },
      onRenameItem: async (itemId: number, title: string, kind: "chat" | "debate") => {
        if (kind === "debate") {
          await handleRenameDebate(itemId, title);
          return;
        }
        await handleRenameConversation(itemId, title);
      },
      onToggleSidebar: toggleSidebar,
      showTitle: true,
      sidebarOpen,
      title: "Chatchat",
    },
    landingProps: {
      draft,
      draftAttachments,
      attachmentUploadAvailable,
      isRecording,
      isStreaming,
      isTranscribing,
      model: selectedModel,
      models: availableModels,
      onAnimationComplete: handleLandingAnimationComplete,
      onChangeDraft: setDraft,
      onModelChange: handleModelChange,
      onRemoveDraftAttachment: removeAttachment,
      onSelectAttachments: addAttachments,
      onSend: () => void handleSend(),
      onStop: handleStop,
      onToggleRecording: handleToggleRecording,
      onToggleRag: handleSelectRag,
      onToggleWeb: handleSelectWeb,
      retrievalMode,
      submitBlocked,
      submitBlockedReason,
      shouldAnimate: !landingHeroAnimated,
      title: landingTitle,
    },
    settingsProps: {
      activeConversationId: activeConversationId && activeConversationId > 0 ? activeConversationId : null,
      activeConversationTitle: activeConversation?.title ?? "",
      knowledge: knowledgeManager,
      memories: memoryManager,
      onClose: () => setSettingsOpen(false),
      open: settingsOpen,
    },
    showLanding,
    sidebarProps: {
      activeConversationId,
      activeDebateId,
      activity: conversationActivity,
      conversationsLoaded,
      debatesLoaded: debateSessionsLoaded,
      isDesktop,
      items: filteredConversations,
      debateItems: filteredDebateSessions,
      onDelete: handleDeleteConversation,
      onDeleteDebate: handleDeleteDebate,
      onNewChat: handleNewChat,
      onOpenSettings: () => setSettingsOpen(true),
      onQueryChange: setQuery,
      onRename: handleRenameConversation,
      onRenameDebate: handleRenameDebate,
      onSelect: handleSelectConversation,
      onSelectDebate: handleSelectDebate,
      onToggleSidebar: toggleSidebar,
      open: sidebarOpen,
      query,
    },
  };
}
