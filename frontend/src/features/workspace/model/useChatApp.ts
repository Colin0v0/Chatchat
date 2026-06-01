import {
  startTransition,
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { pickLandingTitle } from "../../chats/lib/constants";
import { useComposerTranscription } from "../../chats/model/useComposerTranscription";
import { useComposerAttachments } from "../../chats/model/useComposerAttachments";
import { useConversationStreams } from "../../chats/model/useConversationStreams";
import { useChatMessageActions } from "../../chats/model/useChatMessageActions";
import { useChatConversationLifecycle } from "../../chats/model/useChatConversationLifecycle";
import { useKnowledgeManager } from "../../knowledge/model/useKnowledgeManager";
import { useMemoryManager } from "../../memories/model/useMemoryManager";
import { useProjectManager } from "../../projects/model/useProjectManager";
import type { GeneralPreferences } from "../../settings/model/useGeneralPreferences";
import { useDebateMode } from "../../debates/model/useDebateMode";
import { useBattleMode } from "../../battles/model/useBattleMode";
import { useWorkspaceNavigation } from "./useWorkspaceNavigation";
import { usePetCompanionContext } from "./usePetCompanionContext";
import { buildChatAppViewModel } from "./chatAppViewModel";
import { useWorkspaceModels } from "./useWorkspaceModels";
import type { WorkspaceSection } from "./workspaceSections";
import { buildConversationMarkdown, buildDebateMarkdown, downloadMarkdown } from "../../../lib/exportMarkdown";
import {
  loadStoredConversationSummariesCache,
} from "./workspaceCache";
import {
  fileLooksLikeImage,
  toggleToolMode,
} from "./chatAppUtils";
import type { PetSignal, PetSignalType } from "../../pet/model/petSignals";
import type {
  ComposerMode,
  ConversationDetail,
  ConversationSummary,
  ToolMode,
} from "../../../types";

type UseChatAppOptions = {
  closeMobileSidebar: () => void;
  generalPreferences: GeneralPreferences;
  isDesktop: boolean;
  memorySettingsOpen?: boolean;
  onGeneralPreferencesChange: (patch: Partial<GeneralPreferences>) => void;
  onSectionRouteChange?: (section: WorkspaceSection) => void;
  routeSection?: WorkspaceSection;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  userId?: number | null;
};

const DEFAULT_IMAGE_SIZE = "1024x1024";
const DEFAULT_IMAGE_QUALITY = "auto";
const DEFAULT_IMAGE_OUTPUT_FORMAT = "png";

export function useChatApp({
  closeMobileSidebar,
  generalPreferences,
  isDesktop,
  memorySettingsOpen = false,
  onGeneralPreferencesChange,
  onSectionRouteChange,
  routeSection = "chats",
  sidebarOpen,
  toggleSidebar,
  userId,
}: UseChatAppOptions) {
  const [initialConversationSummariesCache] = useState(() => loadStoredConversationSummariesCache());
  const [conversations, setConversations] = useState<ConversationSummary[]>(() => initialConversationSummariesCache ?? []);
  const [conversationsLoaded, setConversationsLoaded] = useState(() => initialConversationSummariesCache !== null);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [activeConversation, setActiveConversation] = useState<ConversationDetail | null>(null);
  const [activeSection, setActiveSection] = useState<WorkspaceSection>(routeSection);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [editingUserMessageId, setEditingUserMessageId] = useState<number | string | null>(null);
  const [editingUserMessageContent, setEditingUserMessageContent] = useState("");
  const [composerMode, setComposerModeState] = useState<ComposerMode>("chat");
  const [imageSize, setImageSize] = useState(DEFAULT_IMAGE_SIZE);
  const [imageQuality, setImageQuality] = useState(DEFAULT_IMAGE_QUALITY);
  const [imageOutputFormat, setImageOutputFormat] = useState(DEFAULT_IMAGE_OUTPUT_FORMAT);
  const [collapsedMessageIds, setCollapsedMessageIds] = useState<Set<number | string>>(new Set());
  const [toolMode, setToolMode] = useState<ToolMode>("none");
  const [knowledgeFolder, setKnowledgeFolder] = useState("");
  const [landingHeroAnimated, setLandingHeroAnimated] = useState(false);
  const [landingTitle] = useState(() => pickLandingTitle());
  const [error, setError] = useState<string | null>(null);
  const [petSignal, setPetSignal] = useState<PetSignal | null>(null);
  const { addAttachments, clearAttachments, draftAttachments, removeAttachment, replaceAttachments } =
    useComposerAttachments();
  const transientAttachmentUrlsRef = useRef<string[]>([]);
  const composerModeRef = useRef<ComposerMode>("chat");
  const chatModelBeforeImageRef = useRef("");
  const deferredQuery = useDeferredValue(query);
  const previousRouteSectionRef = useRef(routeSection);
  const petSignalIdRef = useRef(0);
  const handleResolvedDefaultModel = useCallback((model: string) => {
    onGeneralPreferencesChange({ defaultModel: model });
  }, [onGeneralPreferencesChange]);
  const {
    activeReasoningRequest,
    adjustModelLoveScore,
    adjustModelUsageCount,
    attachmentUploadAvailable,
    availableModels,
    handleModelChange,
    handleReasoningProfileChange,
    imageUploadAvailable,
    reasoningProfile,
    selectedModel,
    setSelectedModel,
  } = useWorkspaceModels({
    defaultModel: generalPreferences.defaultModel,
    onDefaultModelResolved: handleResolvedDefaultModel,
    setError,
  });
  const projectManager = useProjectManager({
    defaultModel: selectedModel,
    enabled: Boolean(userId),
    onError: setError,
    userId,
  });
  const activeProjectId = projectManager.activeProjectId;
  const memoryManager = useMemoryManager({
    activeConversationId: activeConversationId && activeConversationId > 0 ? activeConversationId : null,
    enabled: activeSection === "memories" || memorySettingsOpen,
  });
  const knowledgeManager = useKnowledgeManager({
    enabled: activeSection === "knowledge" || toolMode === "knowledge",
    projectId: activeProjectId,
  });
  const activeKnowledgeFolders = useMemo(
    () => (toolMode === "knowledge" && knowledgeFolder ? [knowledgeFolder] : []),
    [knowledgeFolder, toolMode],
  );
  const emitPetSignal = useCallback((type: PetSignalType) => {
    petSignalIdRef.current += 1;
    setPetSignal({
      id: petSignalIdRef.current,
      type,
    });
  }, []);
  const handleDefaultModelChange = useCallback((model: string) => {
    onGeneralPreferencesChange({ defaultModel: model });
    handleModelChange(model);
  }, [handleModelChange, onGeneralPreferencesChange]);
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

      if (!selectedModel) {
        setError("模型列表还没有加载完成，稍后再试。");
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
    [activeSection, addAttachments, imageUploadAvailable, selectedModel],
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
    projectId: activeProjectId,
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
    projectId: activeProjectId,
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

  useEffect(() => {
    return () => {
      conversationLoadAbortRef.current?.abort();
      earlierMessagesAbortRef.current?.abort();
      abortBattleStreams();
      clearTransientAttachmentUrls();
    };
  }, [abortBattleStreams, clearTransientAttachmentUrls]);

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

  const setComposerModeValue = useCallback((mode: ComposerMode) => {
    composerModeRef.current = mode;
    setComposerModeState(mode);
  }, []);

  const restoreChatComposerMode = useCallback(() => {
    setComposerModeValue("chat");
    if (chatModelBeforeImageRef.current) {
      setSelectedModel(chatModelBeforeImageRef.current);
    }
  }, [setComposerModeValue]);

  const handleComposerModeChange = useCallback(
    (mode: ComposerMode) => {
      if (mode === "image") {
        if (!selectedModel) {
          setError("模型列表还没有加载完成，稍后再试。");
          return;
        }
        chatModelBeforeImageRef.current = selectedModel;
        setComposerModeValue("image");
        return;
      }
      restoreChatComposerMode();
    },
    [restoreChatComposerMode, selectedModel, setComposerModeValue],
  );

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

  const resetProjectScopedView = useCallback(() => {
    conversationLoadAbortRef.current?.abort();
    earlierMessagesAbortRef.current?.abort();
    clearAttachments();
    setActiveConversationId(null);
    setActiveConversation(null);
    setCollapsedMessageIds(new Set());
    setKnowledgeFolder("");
    setDraft("");
  }, [
    clearAttachments,
    conversationLoadAbortRef,
    earlierMessagesAbortRef,
    setActiveConversation,
    setActiveConversationId,
    setCollapsedMessageIds,
    setDraft,
  ]);

  const handleSelectProject = useCallback(
    (projectId: number | null) => {
      projectManager.setActiveProjectId(projectId);
      const project = projectManager.projects.find((item) => item.id === projectId);
      if (project?.default_model) {
        handleModelChange(project.default_model);
      }
      resetProjectScopedView();
      if (!isDesktop) {
        closeMobileSidebar();
      }
    },
    [closeMobileSidebar, handleModelChange, isDesktop, projectManager, resetProjectScopedView],
  );

  const handleCreateProject = useCallback(
    async (name: string) => {
      const project = await projectManager.create(name);
      if (!project) {
        return false;
      }
      if (project.default_model) {
        handleModelChange(project.default_model);
      }
      resetProjectScopedView();
      if (!isDesktop) {
        closeMobileSidebar();
      }
      return true;
    },
    [closeMobileSidebar, handleModelChange, isDesktop, projectManager, resetProjectScopedView],
  );

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
    handleConfirmPendingMemory,
    handleMessageFeedback,
    handleRefreshMessagePendingMemories,
    handleRejectPendingMemory,
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
    projectId: activeProjectId,
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
    temperature: generalPreferences.temperature,
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
  const petContext = usePetCompanionContext({
    activeConversation,
    activeSection,
    battleDraft,
    draft,
    editingUserMessageContent,
    selectedModel,
  });

  return buildChatAppViewModel({
    activeBattleId,
    activeBattleSession,
    activeConversation,
    activeConversationId,
    activeDebate,
    activeDebateId,
    activeProjectId,
    activeReasoningRequest,
    activeSection,
    activeSession,
    attachmentUploadAvailable,
    availableModels,
    battleDraft,
    battleSessionsLoaded,
    battleStreaming,
    collapsedMessageIds,
    composerMode,
    conversationActivity,
    conversationsLoaded,
    debateActivity,
    debateCreateOpen,
    debateRoomProps,
    debateSessionsLoaded,
    draft,
    draftAttachments,
    earlierMessagesError,
    editingUserMessageContent,
    editingUserMessageId,
    error,
    filteredBattleSessions,
    filteredConversations,
    filteredDebateSessions,
    generalPreferences,
    imageOutputFormat,
    imageQuality,
    imageSize,
    isBattleLoading,
    isConversationLoading: activeSection === "chats" && activeConversationId !== null && activeConversation === null,
    isDebateLoading,
    isDesktop,
    isLoadingEarlierMessages,
    isRecording,
    isStreaming,
    isTranscribing,
    knowledgeFolder,
    knowledgeFolders: knowledgeManager.folders,
    knowledgeManager,
    landingHeroAnimated,
    landingTitle,
    memoryManager,
    onAnimationComplete: handleLandingAnimationComplete,
    petContext,
    petDraftActive,
    petSignal,
    petStreaming,
    projectIsSaving: projectManager.isSaving,
    projects: projectManager.projects,
    projectsLoaded: projectManager.loaded,
    query,
    reasoningProfile,
    selectedModel,
    showLanding,
    sidebarOpen,
    submitBlocked,
    submitBlockedReason,
    toolMode,
    visibleStreaming,
    onChangeDefaultModel: handleDefaultModelChange,
    onCancelCreateDebate: handleCancelCreateDebate,
    onCancelEditingUserMessage: handleCancelEditingUserMessage,
    onChangeBattleDraft: setBattleDraft,
    onChangeComposerMode: handleComposerModeChange,
    onChangeDraft: setDraft,
    onChangeEditingUserMessage: setEditingUserMessageContent,
    onChangeGeneralPreferences: onGeneralPreferencesChange,
    onChangeImageOutputFormat: setImageOutputFormat,
    onChangeImageQuality: setImageQuality,
    onChangeImageSize: setImageSize,
    onChangeKnowledgeFolder: setKnowledgeFolder,
    onChangeQuery: setQuery,
    onConfirmPendingMemory: handleConfirmPendingMemory,
    onCreateDebate: handleCreateDebate,
    onCreateProject: handleCreateProject,
    onDeleteBattle: handleDeleteBattle,
    onDeleteConversation: handleDeleteConversation,
    onDeleteDebate: handleDeleteDebate,
    onExportItem: handleExportItem,
    onKnowledgeFolderChange: setKnowledgeFolder,
    onLoadEarlierMessages: handleLoadEarlierMessages,
    onMessageFeedback: handleMessageFeedback,
    onModelChange: handleModelChange,
    onNewBattle: handleNewBattle,
    onNewChat: handleNewChat,
    onNewDebate: handleNewDebate,
    onReasoningProfileChange: handleReasoningProfileChange,
    onRefreshMessagePendingMemories: handleRefreshMessagePendingMemories,
    onRejectPendingMemory: handleRejectPendingMemory,
    onRemoveAttachment: removeAttachment,
    onRenameBattle: handleRenameBattle,
    onRenameConversation: handleRenameConversation,
    onRenameDebate: handleRenameDebate,
    onRenameItem: async (itemId: number, title: string, kind: "chat" | "debate") => {
      if (kind === "debate") {
        await handleRenameDebate(itemId, title);
        return;
      }
      await handleRenameConversation(itemId, title);
    },
    onRestoreChatComposerMode: restoreChatComposerMode,
    onRetryAssistant: handleRetryAssistant,
    onSelectAttachments: handleSelectAttachments,
    onSelectBattle: handleSelectBattle,
    onSelectConversation: handleSelectConversation,
    onSelectDebate: handleSelectDebate,
    onSelectProject: handleSelectProject,
    onSelectSection: handleSelectSection,
    onSend: handleSend,
    onSendBattle: handleSendBattle,
    onStartEditingUserMessage: handleStartEditingUserMessage,
    onStop: handleStop,
    onStopBattle: handleStopBattle,
    onSubmitEditedUserMessage: handleSubmitEditedUserMessage,
    onToggleRag: handleSelectRag,
    onToggleRecording: handleToggleRecording,
    onToggleSidebar: toggleSidebar,
    onToggleWeb: handleSelectWeb,
    onVoteBattle: handleBattleVote,
  });
}
