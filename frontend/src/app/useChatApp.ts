import {
  startTransition,
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

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
  ChatMessage,
  ChatStreamEvent,
  ConversationDetail,
  ConversationSummary,
  ModelOption,
  RagReindexResult,
  ToolPlan,
} from "../types";
import { ASSISTANT_DRAFT_ID, pickLandingTitle } from "./constants";
import {
  createInitialModelOptions,
  createModelOption,
  ensureSelectedModel,
  findModelOption,
  resolveInitialSelectedModel,
} from "./modelOptions";

type ConversationUpdater = (current: ConversationDetail) => ConversationDetail;

type StreamContext = {
  originConversationId: number | null;
  setStreamConversationId: (nextId: number) => number;
  updateVisibleConversation: (updater: ConversationUpdater) => void;
};

type RunStreamOptions = {
  abortMessage: string;
  errorMessage: string;
  initialConversationId: number;
  originConversationId: number | null;
  onEvent: (event: ChatStreamEvent, context: StreamContext) => void;
  request: (handlers: {
    onEvent: (event: ChatStreamEvent) => void;
    signal: AbortSignal;
  }) => Promise<void>;
};

type UseChatAppOptions = {
  closeMobileSidebar: () => void;
  isDesktop: boolean;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
};

function createAssistantDraftMessage(): ChatMessage {
  return {
    id: ASSISTANT_DRAFT_ID,
    role: "assistant",
    content: "",
  };
}

function createUserDraftMessage(id: number | string, content: string): ChatMessage {
  return {
    id,
    role: "user",
    content,
    created_at: new Date().toISOString(),
  };
}

function updateAssistantDraft(
  conversation: ConversationDetail,
  update: (message: ChatMessage) => ChatMessage,
): ConversationDetail {
  return {
    ...conversation,
    messages: conversation.messages.map((item) =>
      item.id === ASSISTANT_DRAFT_ID ? update(item) : item,
    ),
  };
}

function appendAssistantDraftContent(
  conversation: ConversationDetail,
  content: string,
): ConversationDetail {
  return updateAssistantDraft(conversation, (message) => ({
    ...message,
    content: message.content + content,
  }));
}

function setAssistantDraftSources(
  conversation: ConversationDetail,
  sources: ChatMessage["sources"],
): ConversationDetail {
  return updateAssistantDraft(conversation, (message) => ({
    ...message,
    sources,
  }));
}

function setAssistantDraftId(
  conversation: ConversationDetail,
  assistantMessageId: number,
): ConversationDetail {
  return {
    ...conversation,
    messages: conversation.messages.map((item) =>
      item.id === ASSISTANT_DRAFT_ID ? { ...item, id: assistantMessageId } : item,
    ),
  };
}

function replaceConversationMessageId(
  conversation: ConversationDetail,
  fromId: number | string,
  toId: number,
): ConversationDetail {
  return {
    ...conversation,
    messages: conversation.messages.map((item) =>
      item.id === fromId ? { ...item, id: toId } : item,
    ),
  };
}

function replaceAssistantDraftWithError(
  conversation: ConversationDetail,
  message: string,
): ConversationDetail {
  const messages = conversation.messages.filter((item) => item.id !== ASSISTANT_DRAFT_ID);
  return {
    ...conversation,
    messages: [
      ...messages,
      {
        id: ASSISTANT_DRAFT_ID,
        role: "assistant",
        content: message,
      },
    ],
  };
}

function appendRetryDraft(
  conversation: ConversationDetail,
  userMessageId: number | string,
  content: string,
): ConversationDetail {
  const messages = conversation.messages.filter((item) => item.id !== ASSISTANT_DRAFT_ID);
  return {
    ...conversation,
    messages: [
      ...messages,
      createUserDraftMessage(userMessageId, content),
      createAssistantDraftMessage(),
    ],
  };
}

function toStreamErrorMessage(error: unknown, abortMessage: string, fallbackMessage: string) {
  if (error instanceof DOMException && error.name === "AbortError") {
    return abortMessage;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallbackMessage;
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
  const [ragEnabled, setRagEnabled] = useState(false);
  const [webEnabled, setWebEnabled] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingConversationId, setStreamingConversationId] = useState<number | null>(null);
  const [streamingStatusItems, setStreamingStatusItems] = useState<string[]>([]);
  const [streamingToolPlan, setStreamingToolPlan] = useState<ToolPlan | null>(null);
  const [streamingReasoning, setStreamingReasoning] = useState("");
  const [thinkingExpanded, setThinkingExpanded] = useState(false);
  const [landingHeroAnimated, setLandingHeroAnimated] = useState(false);
  const [landingTitle] = useState(() => pickLandingTitle());
  const [error, setError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [isUpdatingRag, setIsUpdatingRag] = useState(false);
  const [ragUpdateError, setRagUpdateError] = useState<string | null>(null);
  const [ragUpdateResult, setRagUpdateResult] = useState<RagReindexResult | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const activeConversationIdRef = useRef<number | null>(null);
  const deferredQuery = useDeferredValue(query);

  const selectedModelOption = useMemo(
    () => findModelOption(models, selectedModel),
    [models, selectedModel],
  );
  const thinkingAvailable = selectedModelOption.supports_thinking;
  const thinkingTraceAvailable = selectedModelOption.supports_thinking_trace;
  const thinkingEnabled =
    thinkingAvailable && selectedModelOption.reasoning_model === selectedModel;

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

  const hasConversation = Boolean(activeConversation && activeConversation.messages.length > 0);
  const visibleStreaming =
    isStreaming &&
    activeConversation !== null &&
    activeConversation.id === streamingConversationId &&
    activeConversation.messages.some((item) => item.id === ASSISTANT_DRAFT_ID);

  const refreshConversations = useCallback(async () => {
    try {
      const items = await fetchConversations();
      setConversations(items);
    } finally {
      setConversationsLoaded(true);
    }
  }, []);

  const loadModels = useCallback(async () => {
    const payload = await fetchModels();
    const nextModels =
      payload.models.length > 0 ? payload.models : [createModelOption(payload.default_model)];
    setModels(nextModels);
    setSelectedModel(resolveInitialSelectedModel(nextModels, payload.default_model));
  }, []);

  const loadConversation = useCallback(async (conversationId: number) => {
    const conversation = await fetchConversation(conversationId);
    setActiveConversation(conversation);
    setSelectedModel(conversation.model);
  }, []);

  useEffect(() => {
    void refreshConversations();
    void loadModels();
  }, [loadModels, refreshConversations]);

  useEffect(() => {
    activeConversationIdRef.current = activeConversationId;
  }, [activeConversationId]);

  useEffect(() => {
    if (activeConversationId === null) {
      return;
    }

    if (isStreaming && activeConversationId === streamingConversationId) {
      return;
    }

    void loadConversation(activeConversationId);
  }, [activeConversationId, isStreaming, loadConversation, streamingConversationId]);

  const resetStreamingState = useCallback(() => {
    setIsStreaming(false);
    setStreamingConversationId(null);
    setStreamingStatusItems([]);
    setStreamingToolPlan(null);
    setStreamingReasoning("");
    setThinkingExpanded(false);
    abortRef.current = null;
  }, []);

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
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }

    startTransition(() => {
      setActiveConversationId(null);
      setActiveConversation(null);
      setCollapsedMessageIds(new Set());
      setDraft("");
      setError(null);
      setIsStreaming(false);
      setStreamingConversationId(null);
      setStreamingStatusItems([]);
      setStreamingToolPlan(null);
      setStreamingReasoning("");
      setThinkingExpanded(false);
      if (!isDesktop) {
        closeMobileSidebar();
      }
    });
  }, [closeMobileSidebar, isDesktop]);

  const handleSelectConversation = useCallback(
    (conversationId: number) => {
      startTransition(() => {
        setActiveConversationId(conversationId);
        setError(null);
        setCollapsedMessageIds(new Set());
        setStreamingStatusItems([]);
        setStreamingToolPlan(null);
        setStreamingReasoning("");
        setThinkingExpanded(false);
        if (!isDesktop) {
          closeMobileSidebar();
        }
      });
    },
    [closeMobileSidebar, isDesktop],
  );

  const handleRenameConversation = useCallback(
    async (conversationId: number, title: string) => {
      await renameConversation(conversationId, title);
      await refreshConversations();
      if (activeConversationId === conversationId) {
        setActiveConversation((current) => (current ? { ...current, title } : current));
      }
    },
    [activeConversationId, refreshConversations],
  );

  const handleDeleteConversation = useCallback(
    async (conversationId: number) => {
      await deleteConversation(conversationId);
      await refreshConversations();

      if (activeConversationId === conversationId) {
        setActiveConversationId(null);
        setActiveConversation(null);
        setCollapsedMessageIds(new Set());
        setDraft("");
      }
    },
    [activeConversationId, refreshConversations],
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

  const runStream = useCallback(
    async ({
      abortMessage,
      errorMessage,
      initialConversationId,
      originConversationId,
      onEvent,
      request,
    }: RunStreamOptions) => {
      let streamConversationId = initialConversationId;

      setError(null);
      setIsStreaming(true);
      setStreamingConversationId(streamConversationId);
      setStreamingStatusItems([]);
      setStreamingToolPlan(null);
      setStreamingReasoning("");
      setThinkingExpanded(false);

      const controller = new AbortController();
      abortRef.current = controller;

      const updateVisibleConversation = (updater: ConversationUpdater) => {
        setActiveConversation((current) => {
          if (!current || current.id !== streamConversationId) {
            return current;
          }

          return updater(current);
        });
      };

      const context: StreamContext = {
        originConversationId,
        setStreamConversationId: (nextId: number) => {
          const previousId = streamConversationId;
          streamConversationId = nextId;
          setStreamingConversationId(nextId);
          return previousId;
        },
        updateVisibleConversation,
      };

      try {
        await request({
          onEvent: (event) => onEvent(event, context),
          signal: controller.signal,
        });

        await refreshConversations();
        if (activeConversationIdRef.current === streamConversationId) {
          await loadConversation(streamConversationId);
        }
      } catch (streamError) {
        setError(toStreamErrorMessage(streamError, abortMessage, errorMessage));
      } finally {
        resetStreamingState();
      }
    },
    [loadConversation, refreshConversations, resetStreamingState],
  );

  const handleStreamEvent = useCallback((event: ChatStreamEvent, context: StreamContext) => {
    if (event.type === "token") {
      setStreamingStatusItems([]);
      context.updateVisibleConversation((current) => appendAssistantDraftContent(current, event.content));
      return;
    }

    if (event.type === "reasoning") {
      setStreamingStatusItems([]);
      setStreamingReasoning((current) => current + event.content);
      return;
    }

    if (event.type === "sources") {
      context.updateVisibleConversation((current) => setAssistantDraftSources(current, event.sources));
      return;
    }

    if (event.type === "status") {
      setStreamingStatusItems(event.items);
      return;
    }

    if (event.type === "tool_plan") {
      setStreamingToolPlan({
        tool: event.tool,
        reason: event.reason,
        run_rag: event.run_rag,
        run_web: event.run_web,
        rag_query: event.rag_query,
        web_query: event.web_query,
      });
      return;
    }

    if (event.type === "error") {
      setStreamingStatusItems([]);
      setError(event.message);
      context.updateVisibleConversation((current) => replaceAssistantDraftWithError(current, event.message));
    }
  }, []);

  const handleSend = useCallback(async () => {
    const message = draft.trim();
    if (!message || isStreaming) {
      return;
    }

    const effectiveModel = selectedModel;
    const tempUserMessage = createUserDraftMessage(`user-${Date.now()}`, message);

    setDraft("");
    setActiveConversation((current) => {
      if (current) {
        return {
          ...current,
          model: effectiveModel,
          messages: [...current.messages, tempUserMessage, createAssistantDraftMessage()],
        };
      }

      return {
        id: 0,
        title: message.slice(0, 48),
        model: effectiveModel,
        messages: [tempUserMessage, createAssistantDraftMessage()],
      };
    });

    await runStream({
      abortMessage: "生成已停止。",
      errorMessage: "发送消息失败。",
      initialConversationId: activeConversationId ?? 0,
      onEvent: (event, context) => {
        if (event.type === "meta") {
          const previousId = context.setStreamConversationId(event.conversation_id);

          if (activeConversationIdRef.current === context.originConversationId) {
            setActiveConversationId(event.conversation_id);
            setSelectedModel(event.model);
          }

          setActiveConversation((current) => {
            if (!current || current.id !== previousId) {
              return current;
            }

            return {
              ...current,
              id: event.conversation_id,
              model: event.model,
            };
          });
          return;
        }

        handleStreamEvent(event, context);
      },
      originConversationId: activeConversationId,
      request: ({ onEvent, signal }) =>
        streamChat(
          {
            conversation_id: activeConversationId,
            message,
            model: effectiveModel,
            use_rag: ragEnabled,
            use_web: webEnabled,
          },
          { onEvent, signal },
        ),
    });
  }, [
    activeConversationId,
    draft,
    handleStreamEvent,
    isStreaming,
    ragEnabled,
    runStream,
    selectedModel,
    webEnabled,
  ]);

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const handleRetryAssistant = useCallback(
    async (messageId: number) => {
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

      setCollapsedMessageIds((current) => new Set([...current, sourceUser.id, messageId]));
      setActiveConversation((current) =>
        current ? appendRetryDraft(current, retryUserDraftId, sourceUser.content) : current,
      );

      await runStream({
        abortMessage: "生成已停止。",
        errorMessage: "重新生成失败。",
        initialConversationId: activeConversation.id,
        onEvent: (event, context) => {
          if (event.type === "meta") {
            const retryMessageId = event.message_id;
            context.setStreamConversationId(event.conversation_id);

            if (activeConversationIdRef.current === context.originConversationId) {
              setSelectedModel(event.model);
            }

            context.updateVisibleConversation((current) =>
              replaceConversationMessageId(current, retryUserDraftId, retryMessageId),
            );
            return;
          }

          if (event.type === "done" && event.assistant_message_id != null) {
            const assistantMessageId = event.assistant_message_id;
            setStreamingStatusItems([]);
            context.updateVisibleConversation((current) =>
              setAssistantDraftId(current, assistantMessageId),
            );
            return;
          }

          handleStreamEvent(event, context);
        },
        originConversationId: activeConversation.id,
        request: ({ onEvent, signal }) =>
          regenerateChat(
            {
              conversation_id: activeConversation.id,
              assistant_message_id: messageId,
              model: effectiveModel,
              use_rag: ragEnabled,
              use_web: webEnabled,
            },
            { onEvent, signal },
          ),
      });
    },
    [activeConversation, handleStreamEvent, isStreaming, ragEnabled, runStream, selectedModel, webEnabled],
  );

  const handleToggleRag = useCallback(() => {
    setRagEnabled((current) => !current);
  }, []);

  const handleToggleWeb = useCallback(() => {
    setWebEnabled((current) => !current);
  }, []);

  const handleToggleThinkingTrace = useCallback(() => {
    setThinkingExpanded((current) => !current);
  }, []);

  const handleLandingAnimationComplete = useCallback(() => {
    setLandingHeroAnimated(true);
  }, []);

  const showLanding = !hasConversation || !activeConversation;

  return {
    error,
    conversationProps: activeConversation
      ? {
          collapsedMessageIds,
          conversation: activeConversation,
          draft,
          isStreaming: visibleStreaming,
          model: selectedModel,
          models: availableModels,
          onChangeDraft: setDraft,
          onModelChange: handleModelChange,
          onRetry: handleRetryAssistant,
          onSend: () => void handleSend(),
          onStop: handleStop,
          onToggleRag: handleToggleRag,
          onToggleThinking: handleToggleThinking,
          onToggleThinkingTrace: handleToggleThinkingTrace,
          onToggleWeb: handleToggleWeb,
          ragEnabled,
          statusItems: visibleStreaming ? streamingStatusItems : [],
          toolPlan: visibleStreaming ? streamingToolPlan : null,
          thinkingAvailable,
          thinkingEnabled,
          thinkingTrace: visibleStreaming ? streamingReasoning : "",
          thinkingTraceAvailable,
          thinkingTraceExpanded: thinkingExpanded,
          webEnabled,
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
      isStreaming,
      model: selectedModel,
      models: availableModels,
      onAnimationComplete: handleLandingAnimationComplete,
      onChangeDraft: setDraft,
      onModelChange: handleModelChange,
      onSend: () => void handleSend(),
      onStop: handleStop,
      onToggleRag: handleToggleRag,
      onToggleThinking: handleToggleThinking,
      onToggleWeb: handleToggleWeb,
      ragEnabled,
      shouldAnimate: !landingHeroAnimated,
      thinkingAvailable,
      thinkingEnabled,
      title: landingTitle,
      webEnabled,
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
