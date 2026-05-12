import {
  startTransition,
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useLatestRequestGuard } from "../../../shared/hooks/useLatestRequestGuard";
import { INITIAL_CHAT_MODEL, pickLandingTitle } from "../../chats/lib/constants";
import { labelForStage } from "../../chats/lib/chatSessionUtils";
import { useComposerTranscription } from "../../chats/model/useComposerTranscription";
import { useComposerAttachments } from "../../chats/model/useComposerAttachments";
import { useConversationStreams } from "../../chats/model/useConversationStreams";
import { useChatMessageActions } from "../../chats/model/useChatMessageActions";
import { useChatConversationLifecycle } from "../../chats/model/useChatConversationLifecycle";
import { useKnowledgeManager } from "../../knowledge/model/useKnowledgeManager";
import { useMemoryManager } from "../../memories/model/useMemoryManager";
import { fetchModels } from "../../models/api/models";
import { useDebateMode } from "../../debates/model/useDebateMode";
import { useBattleMode } from "../../battles/model/useBattleMode";
import { useWorkspaceNavigation } from "./useWorkspaceNavigation";
import {
  createInitialModelOptions,
  createModelOption,
  ensureSelectedModel,
  findModelOption,
  resolveInitialSelectedModel,
} from "../../models/lib/modelOptions";
import {
  normalizeReasoningProfileForModel,
  reasoningRequestValueForModel,
  resolveModelDefaultReasoningProfile,
  resolveModelReasoningControl,
} from "../../models/lib/reasoningProfiles";
import type { WorkspaceSection } from "./workspaceSections";
import { buildConversationMarkdown, buildDebateMarkdown, downloadMarkdown } from "../../../lib/exportMarkdown";
import {
  loadStoredConversationSummariesCache,
  loadStoredModelsCache,
  saveModelsCache,
} from "./workspaceCache";
import type { PetSignal, PetSignalType } from "../../pet/model/petSignals";
import type { PetCompanionContext, PetCompanionContextMessage } from "../../pet/api/petChat";
import type {
  ComposerMode,
  ConversationDetail,
  ChatMessage,
  ConversationSummary,
  ModelOption,
  ModelsPayload,
  ReasoningProfileValue,
  ToolMode,
} from "../../../types";

type UseChatAppOptions = {
  closeMobileSidebar: () => void;
  isDesktop: boolean;
  onSectionRouteChange?: (section: WorkspaceSection) => void;
  routeSection?: WorkspaceSection;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  userId?: number | null;
};

const DEFAULT_IMAGE_SIZE = "1024x1024";
const DEFAULT_IMAGE_QUALITY = "auto";
const DEFAULT_IMAGE_OUTPUT_FORMAT = "png";
const IMAGE_ATTACHMENT_EXTENSIONS = new Set([".gif", ".jpeg", ".jpg", ".png", ".webp"]);
const PET_CONTEXT_MESSAGE_LIMIT = 8;
const PET_CONTEXT_TEXT_LIMIT = 420;

function fileExtension(name: string) {
  const dotIndex = name.lastIndexOf(".");
  return dotIndex >= 0 ? name.slice(dotIndex).toLowerCase() : "";
}

function fileLooksLikeImage(file: File) {
  return file.type.startsWith("image/") || IMAGE_ATTACHMENT_EXTENSIONS.has(fileExtension(file.name));
}

function compactPetContextText(text: string) {
  return text.replace(/\s+/g, " ").trim().slice(0, PET_CONTEXT_TEXT_LIMIT);
}

function toPetContextMessages(messages: ChatMessage[]): PetCompanionContextMessage[] {
  return messages
    .filter((message) => message.role === "user" || message.role === "assistant" || message.role === "system")
    .map((message) => ({
      content: compactPetContextText(message.content),
      role: message.role,
    }))
    .filter((message) => message.content.length > 0)
    .slice(-PET_CONTEXT_MESSAGE_LIMIT);
}

function modelAllowsImageAttachments(model: ModelOption) {
  return model.capabilities?.input.image ?? model.supports_attachment_upload;
}

function toggleToolMode(current: ToolMode, next: Exclude<ToolMode, "none">): ToolMode {
  return current === next ? "none" : next;
}

export function useChatApp({
  closeMobileSidebar,
  isDesktop,
  onSectionRouteChange,
  routeSection = "chats",
  sidebarOpen,
  toggleSidebar,
  userId,
}: UseChatAppOptions) {
  const [initialConversationSummariesCache] = useState(() => loadStoredConversationSummariesCache());
  const [initialModelsCache] = useState(() => loadStoredModelsCache());
  const [conversations, setConversations] = useState<ConversationSummary[]>(() => initialConversationSummariesCache ?? []);
  const [conversationsLoaded, setConversationsLoaded] = useState(() => initialConversationSummariesCache !== null);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [activeConversation, setActiveConversation] = useState<ConversationDetail | null>(null);
  const [activeSection, setActiveSection] = useState<WorkspaceSection>(routeSection);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [editingUserMessageId, setEditingUserMessageId] = useState<number | string | null>(null);
  const [editingUserMessageContent, setEditingUserMessageContent] = useState("");
  const [models, setModels] = useState<ModelOption[]>(() =>
    initialModelsCache?.models.length ? initialModelsCache.models : createInitialModelOptions(),
  );
  const [selectedModel, setSelectedModel] = useState(() =>
    initialModelsCache?.models.length
      ? resolveInitialSelectedModel(initialModelsCache.models, initialModelsCache.default_model)
      : INITIAL_CHAT_MODEL,
  );
  const [composerMode, setComposerModeState] = useState<ComposerMode>("chat");
  const [imageSize, setImageSize] = useState(DEFAULT_IMAGE_SIZE);
  const [imageQuality, setImageQuality] = useState(DEFAULT_IMAGE_QUALITY);
  const [imageOutputFormat, setImageOutputFormat] = useState(DEFAULT_IMAGE_OUTPUT_FORMAT);
  const [reasoningProfile, setReasoningProfile] = useState<ReasoningProfileValue>("off");
  const [collapsedMessageIds, setCollapsedMessageIds] = useState<Set<number | string>>(new Set());
  const [toolMode, setToolMode] = useState<ToolMode>("none");
  const [knowledgeFolder, setKnowledgeFolder] = useState("");
  const [landingHeroAnimated, setLandingHeroAnimated] = useState(false);
  const [landingTitle] = useState(() => pickLandingTitle());
  const [error, setError] = useState<string | null>(null);
  const [petSignal, setPetSignal] = useState<PetSignal | null>(null);
  const memoryManager = useMemoryManager({
    activeConversationId: activeConversationId && activeConversationId > 0 ? activeConversationId : null,
    enabled: activeSection === "memories",
  });
  const knowledgeManager = useKnowledgeManager({ enabled: activeSection === "knowledge" || toolMode === "knowledge" });
  const { addAttachments, clearAttachments, draftAttachments, removeAttachment, replaceAttachments } =
    useComposerAttachments();
  const transientAttachmentUrlsRef = useRef<string[]>([]);
  const composerModeRef = useRef<ComposerMode>("chat");
  const chatModelBeforeImageRef = useRef(INITIAL_CHAT_MODEL);
  const modelsLoadGuard = useLatestRequestGuard();
  const deferredQuery = useDeferredValue(query);
  const reasoningSyncKeyRef = useRef<string | null>(null);
  const previousRouteSectionRef = useRef(routeSection);
  const petSignalIdRef = useRef(0);

  const selectedModelOption = useMemo(
    () => findModelOption(models, selectedModel),
    [models, selectedModel],
  );
  const attachmentUploadAvailable = selectedModelOption.supports_attachment_upload;
  const imageUploadAvailable = modelAllowsImageAttachments(selectedModelOption);
  const selectedModelReasoningKey = useMemo(
    () =>
      [
        selectedModelOption.id,
        resolveModelReasoningControl(selectedModelOption),
        resolveModelDefaultReasoningProfile(selectedModelOption),
      ].join(":"),
    [selectedModelOption],
  );
  const activeReasoningRequest = useMemo(
    () => reasoningRequestValueForModel(selectedModelOption, reasoningProfile),
    [reasoningProfile, selectedModelOption],
  );
  const activeKnowledgeFolders = useMemo(
    () => (toolMode === "knowledge" && knowledgeFolder ? [knowledgeFolder] : []),
    [knowledgeFolder, toolMode],
  );
  const availableModels = useMemo(
    () => ensureSelectedModel(models, selectedModel),
    [models, selectedModel],
  );
  const adjustModelLoveScore = useCallback((modelId: string, delta: number) => {
    setModels((current) =>
      current.map((model) =>
        model.id === modelId
          ? {
              ...model,
              // 中文注释：模型页展示的是喜爱数，点踩只能扣回 0，不能出现负数。
              love_score: Math.max(0, (model.love_score ?? 0) + delta),
            }
          : model,
      ),
    );
  }, []);
  const adjustModelUsageCount = useCallback((modelId: string, delta: number) => {
    setModels((current) =>
      current.map((model) =>
        model.id === modelId
          ? {
              ...model,
              // 中文注释：调用数来自全局统计，本地即时同步时同样保证不会显示负数。
              usage_count: Math.max(0, (model.usage_count ?? 0) + delta),
            }
          : model,
      ),
    );
  }, []);
  const emitPetSignal = useCallback((type: PetSignalType) => {
    petSignalIdRef.current += 1;
    setPetSignal({
      id: petSignalIdRef.current,
      type,
    });
  }, []);
  const {
    activeId: activeDebateId,
    activeSession: activeDebate,
    activity: debateActivity,
    createOpen: debateCreateOpen,
    filteredSessions: filteredDebateSessions,
    isLoading: isDebateLoading,
    loaded: debateSessionsLoaded,
    roomProps: debateRoomProps,
    clearActive: clearActiveDebate,
    createSession: createDebate,
    deleteSession: handleDeleteDebate,
    fetchSessionForExport: fetchDebateSessionForExport,
    openCreate: openDebateCreate,
    renameSession: handleRenameDebate,
    selectSession: selectDebateSession,
  } = useDebateMode({
    query: deferredQuery,
    setError,
    onModelLoveScoreChange: adjustModelLoveScore,
    onModelUsageCountChange: adjustModelUsageCount,
  });
  const {
    activeId: activeBattleId,
    activeSession: activeBattleSession,
    draft: battleDraft,
    filteredSessions: filteredBattleSessions,
    isLoading: isBattleLoading,
    isStreaming: battleStreaming,
    loaded: battleSessionsLoaded,
    abortStreams: abortBattleStreams,
    clearActiveSession: clearActiveBattleSession,
    remove: handleDeleteBattle,
    rename: handleRenameBattle,
    selectSession: selectBattleSession,
    send: handleSendBattle,
    setDraft: setBattleDraft,
    startNewSession: startNewBattleSession,
    stop: handleStopBattle,
    vote: handleBattleVote,
  } = useBattleMode({
    availableModels,
    draftFiles: draftAttachments.map((attachment) => attachment.file),
    knowledgeFolders: activeKnowledgeFolders,
    onDraftAccepted: clearAttachments,
    onModelLoveScoreChange: adjustModelLoveScore,
    onModelUsageCountChange: adjustModelUsageCount,
    onPetEvent: emitPetSignal,
    query: deferredQuery,
    setError,
    toolMode,
    userId: userId ?? null,
  });

  useEffect(() => {
    if (!knowledgeFolder || knowledgeFolder === "__root__") {
      return;
    }
    if (!knowledgeManager.folders.includes(knowledgeFolder)) {
      setKnowledgeFolder("");
    }
  }, [knowledgeFolder, knowledgeManager.folders]);

  const clearTransientAttachmentUrls = useCallback(() => {
    transientAttachmentUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    transientAttachmentUrlsRef.current = [];
  }, []);

  const handleSelectAttachments = useCallback(
    (files: FileList | File[]) => {
      const selectedFiles = Array.from(files);
      if (selectedFiles.length === 0) {
        return;
      }

      if (activeSection === "battle") {
        addAttachments(selectedFiles);
        return;
      }

      const allowedFiles = imageUploadAvailable
        ? selectedFiles
        : selectedFiles.filter((file) => !fileLooksLikeImage(file));
      if (allowedFiles.length < selectedFiles.length) {
        setError("当前模型不支持图片上传，请切换到 Claude/Gemini/Codex 等多模态模型。");
      }
      if (allowedFiles.length > 0) {
        addAttachments(allowedFiles);
      }
    },
    [activeSection, addAttachments, imageUploadAvailable],
  );

  const {
    abortAndRemoveSession,
    activeSession,
    attachActiveStream,
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
  });
  const {
    cancelRecording,
    isRecording,
    isTranscribing,
    onToggleRecording: handleToggleRecording,
  } = useComposerTranscription({
    isStreaming,
    setDraft,
    setError,
  });
  const submitBlocked = composerMode === "image" && draftAttachments.length > 0;
  const submitBlockedReason = submitBlocked ? "生成图片暂不支持附件，请先移除附件。" : null;

  const {
    conversationLoadAbortRef,
    earlierMessagesAbortRef,
    earlierMessagesError,
    filteredConversations,
    handleDeleteConversation,
    handleLoadEarlierMessages,
    handleRenameConversation,
    isLoadingEarlierMessages,
    loadFullConversationForExport,
    refreshConversations,
  } = useChatConversationLifecycle({
    abortAndRemoveSession,
    activeConversation,
    activeConversationId,
    activeSession,
    attachActiveStream,
    cancelRecording,
    clearAttachments,
    conversations,
    deferredQuery,
    getSessionConversation,
    mergeConversationSummariesWithSessions,
    renameSession,
    runningSessions,
    setActiveConversation,
    setActiveConversationId,
    setCollapsedMessageIds,
    setConversations,
    setConversationsLoaded,
    setDraft,
    setEditingUserMessageContent,
    setEditingUserMessageId,
    setError,
    setSelectedModel,
  });

  useEffect(() => {
    if (previousRouteSectionRef.current === routeSection) {
      return;
    }

    previousRouteSectionRef.current = routeSection;
    startTransition(() => {
      setActiveSection(routeSection);
      if (routeSection === "chats") {
        setActiveConversationId(null);
        setActiveConversation(null);
        clearActiveDebate();
        clearActiveBattleSession();
        setCollapsedMessageIds(new Set());
        return;
      }
      if (routeSection === "battle") {
        setActiveConversationId(null);
        setActiveConversation(null);
        clearActiveDebate();
        setCollapsedMessageIds(new Set());
      }
    });
  }, [clearActiveBattleSession, clearActiveDebate, routeSection]);

  const loadModels = useCallback(async () => {
    const requestId = modelsLoadGuard.begin();
    try {
      const payload = await fetchModels();
      if (!modelsLoadGuard.isCurrent(requestId)) {
        return;
      }
      const nextModels =
        payload.models.length > 0 ? payload.models : [createModelOption(payload.default_model)];
      saveModelsCache({
        default_model: payload.default_model,
        models: nextModels,
      } satisfies ModelsPayload);
      setModels(nextModels);
      setSelectedModel(resolveInitialSelectedModel(nextModels, payload.default_model));
    } catch (loadError) {
      if (modelsLoadGuard.isCurrent(requestId)) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load models.");
      }
    }
  }, [modelsLoadGuard, setError]);

  useEffect(() => {
    void loadModels();
  }, [loadModels]);

  useEffect(() => {
    return () => {
      conversationLoadAbortRef.current?.abort();
      earlierMessagesAbortRef.current?.abort();
      abortBattleStreams();
      clearTransientAttachmentUrls();
    };
  }, [abortBattleStreams, clearTransientAttachmentUrls]);

  useEffect(() => {
    if (reasoningSyncKeyRef.current === selectedModelReasoningKey) {
      return;
    }
    reasoningSyncKeyRef.current = selectedModelReasoningKey;
    setReasoningProfile(
      normalizeReasoningProfileForModel(
        selectedModelOption,
        resolveModelDefaultReasoningProfile(selectedModelOption),
      ),
    );
  }, [selectedModelOption, selectedModelReasoningKey]);

  useEffect(() => {
    if (!error) {
      return;
    }

    const timeoutId = window.setTimeout(() => setError(null), 5000);
    return () => window.clearTimeout(timeoutId);
  }, [error]);

  useEffect(() => {
    if (!error) {
      return;
    }

    // 错误提示一出现，宠物就给出一次明确的“出错”反应，不跟着每次渲染重复抖动。
    emitPetSignal("error");
  }, [emitPetSignal, error]);

  const handleModelChange = useCallback((model: string) => {
    setSelectedModel(model);
  }, []);

  const setComposerModeValue = useCallback((mode: ComposerMode) => {
    composerModeRef.current = mode;
    setComposerModeState(mode);
  }, []);

  const restoreChatComposerMode = useCallback(() => {
    setComposerModeValue("chat");
    setSelectedModel(chatModelBeforeImageRef.current);
  }, [setComposerModeValue]);

  const handleComposerModeChange = useCallback(
    (mode: ComposerMode) => {
      if (mode === "image") {
        chatModelBeforeImageRef.current = selectedModel;
        setComposerModeValue("image");
        return;
      }
      restoreChatComposerMode();
    },
    [restoreChatComposerMode, selectedModel, setComposerModeValue],
  );

  const handleReasoningProfileChange = useCallback((value: ReasoningProfileValue) => {
    setReasoningProfile(normalizeReasoningProfileForModel(selectedModelOption, value));
  }, [selectedModelOption]);

  const {
    handleCancelCreateDebate,
    handleCreateDebate,
    handleNewChat,
    handleNewDebate,
    handleSelectBattle,
    handleSelectConversation,
    handleSelectDebate,
    handleSelectSection,
  } = useWorkspaceNavigation({
    cancelRecording,
    clearActiveBattleSession,
    clearActiveDebate,
    clearAttachments,
    closeMobileSidebar,
    conversationLoadAbortRef,
    createDebate,
    earlierMessagesAbortRef,
    isDesktop,
    onSectionRouteChange,
    openDebateCreate,
    openSessionConversation,
    selectBattleSession,
    selectDebateSession,
    setActiveConversation,
    setActiveConversationId,
    setActiveSection,
    setCollapsedMessageIds,
    setDraft,
    setError,
    startNewBattleSession,
  });

  const handleNewBattle = useCallback(() => {
    handleSelectSection("battle");
  }, [handleSelectSection]);

  const handleExportItem = useCallback(
    async (itemId: number, kind: "chat" | "debate") => {
      try {
        if (kind === "debate") {
          const session = await fetchDebateSessionForExport(itemId);
          downloadMarkdown(session.topic || `debate-${itemId}`, buildDebateMarkdown(session));
          return;
        }

        const conversation = await loadFullConversationForExport(itemId);
        downloadMarkdown(
          conversation.title || `chat-${itemId}`,
          buildConversationMarkdown(conversation),
        );
      } catch (exportError) {
        setError(exportError instanceof Error ? exportError.message : "Failed to export markdown.");
      }
    },
    [fetchDebateSessionForExport, loadFullConversationForExport, setError],
  );

  const {
    handleCancelEditingUserMessage,
    handleMessageFeedback,
    handleRetryAssistant,
    handleSend,
    handleStartEditingUserMessage,
    handleStop,
    handleSubmitEditedUserMessage,
  } = useChatMessageActions({
    activeConversation,
    activeKnowledgeFolders,
    activeReasoningRequest,
    chatModelBeforeImageRef,
    clearAttachments,
    composerModeRef,
    draft,
    draftAttachments,
    editingUserMessageContent,
    imageOutputFormat,
    imageQuality,
    imageSize,
    imageUploadAvailable,
    isRecording,
    isStreaming,
    isTranscribing,
    onModelLoveScoreChange: adjustModelLoveScore,
    onModelUsageCountChange: adjustModelUsageCount,
    onPetEvent: emitPetSignal,
    refreshConversations,
    replaceAttachments,
    restoreChatComposerMode,
    runStream,
    selectedModel,
    setActiveConversation,
    setActiveConversationId,
    setCollapsedMessageIds,
    setDraft,
    setEditingUserMessageContent,
    setEditingUserMessageId,
    setError,
    stopStream,
    toolMode,
    transientAttachmentUrlsRef,
  });

  const handleSelectRag = useCallback(() => {
    setToolMode((current) => toggleToolMode(current, "knowledge"));
  }, []);

  const handleSelectWeb = useCallback(() => {
    setToolMode((current) => toggleToolMode(current, "search"));
  }, []);

  const handleLandingAnimationComplete = useCallback(() => {
    setLandingHeroAnimated(true);
  }, []);

  const showLanding =
    activeSection === "chats" &&
    !debateCreateOpen &&
    activeDebateId === null &&
    activeConversationId === null &&
    (!activeConversation || activeConversation.messages.length === 0);
  const showSessionHeaderActions =
    activeSection === "chats" || activeSection === "debates";
  const showChatModelSelector = activeSection === "chats" && composerMode !== "image";
  const workspaceTitle =
    activeSection === "battle"
      ? "Chatchat: Battle"
      : activeSection === "debates"
        ? "Chatchat: Debate"
        : "Chatchat";
  const petDraftActive =
    activeSection === "battle"
      ? battleDraft.trim().length > 0
      : draft.trim().length > 0 || editingUserMessageContent.trim().length > 0;
  const petStreaming =
    activeSection === "battle"
      ? battleStreaming
      : activeSection === "chats"
        ? visibleStreaming
        : false;
  const petContext = useMemo<PetCompanionContext>(() => {
    const activeDraft = activeSection === "battle"
      ? battleDraft
      : editingUserMessageContent.trim()
        ? editingUserMessageContent
        : draft;

    return {
      activeSection,
      conversation: activeSection === "chats" && activeConversation
        ? {
            id: activeConversation.id,
            messages: toPetContextMessages(activeConversation.messages),
            model: activeConversation.model || selectedModel,
            title: activeConversation.title,
          }
        : null,
      draft: compactPetContextText(activeDraft),
    };
  }, [activeConversation, activeSection, battleDraft, draft, editingUserMessageContent, selectedModel]);

  return {
    activeSection,
    error,
    battlePageProps: {
      composerProps: {
        attachmentUploadAvailable: true,
        attachments: draftAttachments,
        centered: true,
        composerMode: "chat" as const,
        isRecording: false,
        isStreaming: battleStreaming,
        isTranscribing: false,
        knowledgeFolder,
        knowledgeFolders: knowledgeManager.folders,
        model: selectedModel,
        models: availableModels,
        onChange: setBattleDraft,
        onComposerModeChange: restoreChatComposerMode,
        onKnowledgeFolderChange: setKnowledgeFolder,
        onModelChange: handleModelChange,
        onNewDebate: handleNewDebate,
        onNewBattle: handleNewBattle,
        onReasoningProfileChange: handleReasoningProfileChange,
        onRemoveAttachment: removeAttachment,
        onSelectAttachments: handleSelectAttachments,
        onStop: handleStopBattle,
        onSubmit: () => void handleSendBattle(),
        onToggleRag: handleSelectRag,
        onToggleRecording: handleToggleRecording,
        onToggleWeb: handleSelectWeb,
        reasoningProfile,
        showNewBattleOption: false,
        submitBlocked: false,
        submitBlockedReason: null,
        toolMode,
        value: battleDraft,
      },
      isStreaming: battleStreaming,
      session: activeBattleSession,
      onVote: handleBattleVote,
    },
    debateCreateProps: debateCreateOpen
      ? {
          defaultProModelId: selectedModel,
          defaultConModelId: selectedModel,
          models: availableModels,
          onCancel: handleCancelCreateDebate,
          onCreate: handleCreateDebate,
        }
      : null,
    debateRoomProps,
    conversationProps: activeConversation
      ? {
          canLoadEarlierMessages: activeConversation.remaining_message_count > 0,
          collapsedMessageIds,
          conversation: activeConversation,
          draft,
          draftAttachments,
          editingUserMessageContent,
          editingUserMessageId,
          attachmentUploadAvailable,
          earlierMessagesError,
          isLoadingEarlierMessages,
          isRecording,
          isReasoningStreaming: activeSession?.reasoningStreaming ?? false,
          isStreaming: visibleStreaming,
          isTranscribing,
          model: selectedModel,
          models: availableModels,
          composerMode,
          reserveThinkingSpace: activeReasoningRequest !== null && activeReasoningRequest !== "off",
          reasoningProfile,
          knowledgeFolders: knowledgeManager.folders,
          knowledgeFolder,
          onChangeDraft: setDraft,
          onComposerModeChange: handleComposerModeChange,
          onFeedback: (messageId: number, value: "up" | "down" | null) =>
            void handleMessageFeedback(messageId, value),
          onLoadEarlierMessages: () => void handleLoadEarlierMessages(),
          onModelChange: handleModelChange,
          onReasoningProfileChange: handleReasoningProfileChange,
          onKnowledgeFolderChange: setKnowledgeFolder,
          onCancelEditingUserMessage: handleCancelEditingUserMessage,
          onChangeEditingUserMessage: setEditingUserMessageContent,
          onRemoveDraftAttachment: removeAttachment,
          onRetry: handleRetryAssistant,
          onStartEditingUserMessage: handleStartEditingUserMessage,
          onSubmitEditingUserMessage: (messageId: number | string) => void handleSubmitEditedUserMessage(messageId),
          onSelectAttachments: handleSelectAttachments,
          onNewDebate: handleNewDebate,
          onNewBattle: handleNewBattle,
          onSend: () => void handleSend(),
          onStop: handleStop,
          onToggleRecording: handleToggleRecording,
          onToggleRag: handleSelectRag,
          onToggleWeb: handleSelectWeb,
          toolMode,
          submitBlocked,
          submitBlockedReason,
          showNewBattleOption: true,
          streamingStatusLabel: visibleStreaming ? labelForStage(activeSession?.stage ?? null) : null,
        }
      : null,
    headerProps: {
      activeItemId: showSessionHeaderActions
        ? activeSection === "debates"
          ? activeDebateId
          : activeConversationId
        : null,
      activeItemKind:
        showSessionHeaderActions
          ? activeSection === "debates"
            ? activeDebateId !== null
              ? ("debate" as const)
              : null
            : activeConversationId !== null
              ? ("chat" as const)
              : null
          : null,
      activeItemTitle: activeDebate?.topic ?? activeConversation?.title ?? "",
      isDesktop,
      mobileModel: showChatModelSelector ? selectedModel : "",
      mobileModels: showChatModelSelector ? availableModels : [],
      onNewChat: handleNewChat,
      onNewDebate: handleNewDebate,
      onDeleteItem: async (itemId: number, kind: "chat" | "debate") => {
        if (kind === "debate") {
          await handleDeleteDebate(itemId);
          return;
        }
        await handleDeleteConversation(itemId);
      },
      onExportItem: async (itemId: number, kind: "chat" | "debate") => {
        await handleExportItem(itemId, kind);
      },
      onRenameItem: async (itemId: number, title: string, kind: "chat" | "debate") => {
        if (kind === "debate") {
          await handleRenameDebate(itemId, title);
          return;
        }
        await handleRenameConversation(itemId, title);
      },
      onMobileModelChange: showChatModelSelector ? handleModelChange : undefined,
      onToggleSidebar: toggleSidebar,
      showTitle: true,
      sidebarOpen,
      title: workspaceTitle,
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
      composerMode,
      reasoningProfile,
      knowledgeFolders: knowledgeManager.folders,
      knowledgeFolder,
      onAnimationComplete: handleLandingAnimationComplete,
      onChangeDraft: setDraft,
      onComposerModeChange: handleComposerModeChange,
      onModelChange: handleModelChange,
      onReasoningProfileChange: handleReasoningProfileChange,
      onKnowledgeFolderChange: setKnowledgeFolder,
      onRemoveDraftAttachment: removeAttachment,
      onSelectAttachments: handleSelectAttachments,
      onNewDebate: handleNewDebate,
      onNewBattle: handleNewBattle,
      onSend: () => void handleSend(),
      onStop: handleStop,
      onToggleRecording: handleToggleRecording,
      onToggleRag: handleSelectRag,
      onToggleWeb: handleSelectWeb,
      toolMode,
      submitBlocked,
      submitBlockedReason,
      showNewBattleOption: true,
      shouldAnimate: !landingHeroAnimated,
      title: landingTitle,
    },
    imageSettingsProps: {
      imageSize,
      imageQuality,
      imageOutputFormat,
      onImageSizeChange: setImageSize,
      onImageQualityChange: setImageQuality,
      onImageOutputFormatChange: setImageOutputFormat,
    },
    knowledgePageProps: {
      knowledge: knowledgeManager,
    },
    memoriesPageProps: {
      activeConversationId: activeConversationId && activeConversationId > 0 ? activeConversationId : null,
      activeConversationTitle: activeConversation?.title ?? "",
      memories: memoryManager,
    },
    petActivity: {
      context: petContext,
      draftActive: petDraftActive,
      isStreaming: petStreaming,
      signal: petSignal,
    },
    modelsPageProps: {
      models: availableModels,
      onSelectModel: handleModelChange,
      selectedModel,
    },
    isBattleLoading,
    isConversationLoading: activeSection === "chats" && activeConversationId !== null && activeConversation === null,
    isDebateLoading,
    showLanding,
    sidebarProps: {
      activeSection,
      activeConversationId,
      activeDebateId,
      activeBattleId,
      activity: conversationActivity,
      debateActivity,
      battlesLoaded: battleSessionsLoaded,
      conversationsLoaded,
      debatesLoaded: debateSessionsLoaded,
      isDesktop,
      items: filteredConversations,
      debateItems: filteredDebateSessions,
      battleItems: filteredBattleSessions,
      onSelectSection: handleSelectSection,
      onDelete: handleDeleteConversation,
      onDeleteDebate: handleDeleteDebate,
      onDeleteBattle: handleDeleteBattle,
      onNewChat: handleNewChat,
      onNewDebate: handleNewDebate,
      onQueryChange: setQuery,
      onRename: handleRenameConversation,
      onRenameDebate: handleRenameDebate,
      onRenameBattle: handleRenameBattle,
      onSelect: handleSelectConversation,
      onSelectDebate: handleSelectDebate,
      onSelectBattle: handleSelectBattle,
      onToggleSidebar: toggleSidebar,
      open: sidebarOpen,
      query,
    },
  };
}
