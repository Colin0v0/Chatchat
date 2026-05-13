import type { ComponentProps } from "react";

import { labelForStage, type StreamingStage } from "../../chats/lib/chatSessionUtils";
import { ConversationView } from "../../chats/ui/ConversationView";
import { LandingView } from "../../chats/ui/LandingView";
import { BattlePage } from "../../battles/ui/BattlePage";
import { DebateCreateView } from "../../debates/ui/DebateCreateView";
import { DebateRoomView } from "../../debates/ui/DebateRoomView";
import { KnowledgePage } from "../../knowledge/ui/KnowledgePage";
import { MemoriesPage } from "../../memories/ui/MemoriesPage";
import { ModelsPage } from "../../models/ui/ModelsPage";
import { MainHeader } from "../ui/MainHeader";
import type { SidebarProps } from "../ui/sidebar/types";
import type { PetCompanionContext } from "../../pet/api/petChat";
import type { PetSignal } from "../../pet/model/petSignals";
import type { GeneralPreferences } from "../../settings/model/useGeneralPreferences";
import type {
  ComposerMode,
  ConversationDetail,
  ConversationSummary,
  FeedbackValue,
  MemoryCandidateUpdatePayload,
  MemorySettings,
  ModelOption,
  ReasoningProfileValue,
  ToolMode,
} from "../../../types";
import type { WorkspaceSection } from "./workspaceSections";

type ConversationViewProps = ComponentProps<typeof ConversationView>;
type LandingViewProps = ComponentProps<typeof LandingView>;
type BattlePageProps = ComponentProps<typeof BattlePage>;
type DebateCreateProps = ComponentProps<typeof DebateCreateView>;
type DebateRoomProps = ComponentProps<typeof DebateRoomView>;
type KnowledgePageProps = ComponentProps<typeof KnowledgePage>;
type MemoriesPageProps = ComponentProps<typeof MemoriesPage>;
type ModelsPageProps = ComponentProps<typeof ModelsPage>;
type MainHeaderProps = ComponentProps<typeof MainHeader>;
type SidebarRootProps = Omit<SidebarProps, "onOpenSearch">;
type MemoryManagerProps = MemoriesPageProps["memories"] & {
  settings: MemorySettings;
  onChangeSettings: (patch: Partial<MemorySettings>) => void;
  onClearChatHistoryIndex: () => void;
  onClearSavedMemories: () => void;
};

export interface ChatAppViewModel {
  activeSection: WorkspaceSection;
  battlePageProps: BattlePageProps;
  conversationProps: ConversationViewProps | null;
  debateCreateProps: DebateCreateProps | null;
  debateRoomProps: DebateRoomProps | null;
  error: string | null;
  headerProps: MainHeaderProps;
  generalSettingsProps: {
    availableModels: ModelOption[];
    defaultModel: string;
    temperature: number;
    onDefaultModelChange: (value: string) => void;
    onTemperatureChange: (value: number) => void;
  };
  imageSettingsProps: {
    imageSize: string;
    imageQuality: string;
    imageOutputFormat: string;
    onImageSizeChange: (value: string) => void;
    onImageQualityChange: (value: string) => void;
    onImageOutputFormatChange: (value: string) => void;
  };
  memorySettingsProps: {
    isSaving: boolean;
    settings: MemorySettings;
    onChangeSettings: (patch: Partial<MemorySettings>) => void;
    onClearChatHistoryIndex: () => void;
    onClearSavedMemories: () => void;
  };
  isBattleLoading: boolean;
  isConversationLoading: boolean;
  isDebateLoading: boolean;
  knowledgePageProps: KnowledgePageProps;
  landingProps: LandingViewProps;
  memoriesPageProps: MemoriesPageProps;
  modelsPageProps: ModelsPageProps;
  petActivity: {
    context: PetCompanionContext;
    draftActive: boolean;
    isStreaming: boolean;
    signal: PetSignal | null;
  };
  showLanding: boolean;
  sidebarProps: SidebarRootProps;
}

interface BuildChatAppViewModelOptions {
  activeBattleId: number | null;
  activeBattleSession: BattlePageProps["session"];
  activeConversation: ConversationDetail | null;
  activeConversationId: number | null;
  activeDebate: { topic?: string | null } | null;
  activeDebateId: number | null;
  activeReasoningRequest: string | null;
  activeSection: WorkspaceSection;
  activeSession: { reasoningStreaming?: boolean; stage?: StreamingStage | null } | null | undefined;
  attachmentUploadAvailable: boolean;
  availableModels: ModelOption[];
  battleDraft: string;
  battleSessionsLoaded: boolean;
  battleStreaming: boolean;
  collapsedMessageIds: Set<number | string>;
  composerMode: ComposerMode;
  conversationActivity: Record<number, { running: boolean; unread: boolean }>;
  conversationsLoaded: boolean;
  debateActivity: Record<number, { running: boolean; unread: boolean }>;
  debateCreateOpen: boolean;
  debateRoomProps: DebateRoomProps | null;
  debateSessionsLoaded: boolean;
  draft: string;
  draftAttachments: BattlePageProps["composerProps"]["attachments"];
  earlierMessagesError: string | null;
  editingUserMessageContent: string;
  editingUserMessageId: number | string | null;
  error: string | null;
  filteredBattleSessions: SidebarProps["battleItems"];
  filteredConversations: ConversationSummary[];
  filteredDebateSessions: SidebarProps["debateItems"];
  generalPreferences: GeneralPreferences;
  imageOutputFormat: string;
  imageQuality: string;
  imageSize: string;
  isBattleLoading: boolean;
  isConversationLoading: boolean;
  isDebateLoading: boolean;
  isDesktop: boolean;
  isLoadingEarlierMessages: boolean;
  isRecording: boolean;
  isStreaming: boolean;
  isTranscribing: boolean;
  knowledgeFolder: string;
  knowledgeFolders: string[];
  knowledgeManager: KnowledgePageProps["knowledge"];
  landingHeroAnimated: boolean;
  landingTitle: string;
  memoryManager: MemoryManagerProps;
  onAnimationComplete: () => void;
  petContext: PetCompanionContext;
  petDraftActive: boolean;
  petSignal: PetSignal | null;
  petStreaming: boolean;
  query: string;
  reasoningProfile: ReasoningProfileValue;
  selectedModel: string;
  showLanding: boolean;
  sidebarOpen: boolean;
  submitBlocked: boolean;
  submitBlockedReason: string | null;
  toolMode: ToolMode;
  visibleStreaming: boolean;
  onChangeDefaultModel: (value: string) => void;
  onCancelCreateDebate: () => void;
  onCancelEditingUserMessage: () => void;
  onChangeBattleDraft: (value: string) => void;
  onChangeComposerMode: (mode: ComposerMode) => void;
  onChangeEditingUserMessage: (value: string) => void;
  onChangeDraft: (value: string) => void;
  onChangeImageOutputFormat: (value: string) => void;
  onChangeImageQuality: (value: string) => void;
  onChangeImageSize: (value: string) => void;
  onChangeGeneralPreferences: (patch: Partial<GeneralPreferences>) => void;
  onChangeKnowledgeFolder: (value: string) => void;
  onChangeQuery: (value: string) => void;
  onConfirmPendingMemory: (memoryId: number, payload?: MemoryCandidateUpdatePayload) => Promise<void> | void;
  onCreateDebate: ComponentProps<typeof DebateCreateView>["onCreate"];
  onDeleteBattle: (sessionId: number) => void | Promise<void>;
  onDeleteConversation: (conversationId: number) => void | Promise<void>;
  onDeleteDebate: (sessionId: number) => void | Promise<void>;
  onExportItem: (itemId: number, kind: "chat" | "debate") => Promise<void>;
  onKnowledgeFolderChange: (value: string) => void;
  onLoadEarlierMessages: () => Promise<void> | void;
  onMessageFeedback: (messageId: number, value: FeedbackValue | null) => Promise<void> | void;
  onModelChange: (value: string) => void;
  onNewBattle: () => void;
  onNewChat: () => void;
  onNewDebate: () => void;
  onReasoningProfileChange: (value: ReasoningProfileValue) => void;
  onRefreshMessagePendingMemories: (messageId: number) => Promise<void> | void;
  onRejectPendingMemory: (memoryId: number) => Promise<void> | void;
  onRemoveAttachment: (attachmentId: string) => void;
  onRenameBattle: (sessionId: number, title: string) => void | Promise<void>;
  onRenameConversation: (conversationId: number, title: string) => void | Promise<void>;
  onRenameDebate: (sessionId: number, topic: string) => void | Promise<void>;
  onRenameItem: (itemId: number, title: string, kind: "chat" | "debate") => Promise<void>;
  onRetryAssistant: (messageId: number | string) => void;
  onSelectAttachments: (files: FileList | File[]) => void;
  onSelectBattle: (sessionId: number) => void;
  onSelectConversation: (conversationId: number) => void;
  onSelectDebate: (sessionId: number) => void;
  onSelectSection: (section: WorkspaceSection) => void;
  onSend: () => Promise<void> | void;
  onSendBattle: () => Promise<void> | void;
  onStartEditingUserMessage: (messageId: number | string) => void;
  onStop: () => void;
  onStopBattle: () => void;
  onSubmitEditedUserMessage: (messageId: number | string) => Promise<void> | void;
  onToggleRag: () => void;
  onToggleRecording: () => void;
  onToggleSidebar: () => void;
  onToggleWeb: () => void;
  onVoteBattle: BattlePageProps["onVote"];
  onRestoreChatComposerMode: (mode: ComposerMode) => void;
}

export function buildChatAppViewModel(options: BuildChatAppViewModelOptions): ChatAppViewModel {
  const {
    activeBattleId,
    activeBattleSession,
    activeConversation,
    activeConversationId,
    activeDebate,
    activeDebateId,
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
    isConversationLoading,
    isDebateLoading,
    isDesktop,
    isLoadingEarlierMessages,
    isRecording,
    isStreaming,
    isTranscribing,
    knowledgeFolder,
    knowledgeFolders,
    knowledgeManager,
    landingHeroAnimated,
    landingTitle,
    memoryManager,
    petContext,
    petDraftActive,
    petSignal,
    petStreaming,
    query,
    reasoningProfile,
    selectedModel,
    showLanding,
    sidebarOpen,
    submitBlocked,
    submitBlockedReason,
    toolMode,
    visibleStreaming,
    onChangeDefaultModel,
    onCancelCreateDebate,
    onCancelEditingUserMessage,
    onChangeBattleDraft,
    onChangeComposerMode,
    onChangeEditingUserMessage,
    onChangeDraft,
    onChangeGeneralPreferences,
    onChangeImageOutputFormat,
    onChangeImageQuality,
    onChangeImageSize,
    onChangeKnowledgeFolder,
    onChangeQuery,
    onConfirmPendingMemory,
    onCreateDebate,
    onDeleteBattle,
    onDeleteConversation,
    onDeleteDebate,
    onExportItem,
    onKnowledgeFolderChange,
    onMessageFeedback,
    onModelChange,
    onNewBattle,
    onNewChat,
    onNewDebate,
    onReasoningProfileChange,
    onRefreshMessagePendingMemories,
    onRejectPendingMemory,
    onRemoveAttachment,
    onRenameBattle,
    onRenameConversation,
    onRenameDebate,
    onRenameItem,
    onRetryAssistant,
    onSelectAttachments,
    onSelectBattle,
    onSelectConversation,
    onSelectDebate,
    onSelectSection,
    onSend,
    onSendBattle,
    onStartEditingUserMessage,
    onStop,
    onStopBattle,
    onSubmitEditedUserMessage,
    onToggleRag,
    onToggleRecording,
    onToggleSidebar,
    onToggleWeb,
    onVoteBattle,
    onRestoreChatComposerMode,
  } = options;

  const showSessionHeaderActions = activeSection === "chats" || activeSection === "debates";
  const showChatModelSelector = activeSection === "chats" && composerMode !== "image";
  const workspaceTitle =
    activeSection === "battle"
      ? "Chatchat: Battle"
      : activeSection === "debates"
        ? "Chatchat: Debate"
        : "Chatchat";

  return {
    activeSection,
    error,
    battlePageProps: {
      composerProps: {
        attachmentUploadAvailable: true,
        attachments: draftAttachments,
        centered: true,
        composerMode: "chat",
        isRecording: false,
        isStreaming: battleStreaming,
        isTranscribing: false,
        knowledgeFolder,
        knowledgeFolders,
        model: selectedModel,
        models: availableModels,
        onChange: onChangeBattleDraft,
        onComposerModeChange: onRestoreChatComposerMode,
        onKnowledgeFolderChange,
        onModelChange,
        onNewBattle,
        onNewDebate,
        onReasoningProfileChange,
        onRemoveAttachment,
        onSelectAttachments,
        onStop: onStopBattle,
        onSubmit: () => void onSendBattle(),
        onToggleRag,
        onToggleRecording,
        onToggleWeb,
        reasoningProfile,
        showNewBattleOption: false,
        submitBlocked: false,
        submitBlockedReason: null,
        toolMode,
        value: battleDraft,
      },
      isStreaming: battleStreaming,
      session: activeBattleSession,
      onVote: onVoteBattle,
    },
    debateCreateProps: debateCreateOpen
      ? {
          defaultProModelId: selectedModel,
          defaultConModelId: selectedModel,
          models: availableModels,
          onCancel: onCancelCreateDebate,
          onCreate: onCreateDebate,
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
          knowledgeFolders,
          knowledgeFolder,
          onChangeDraft,
          onComposerModeChange: onChangeComposerMode,
          onFeedback: (messageId: number, value: FeedbackValue | null) => void onMessageFeedback(messageId, value),
          onConfirmPendingMemory,
          onLoadEarlierMessages: () => void options.onLoadEarlierMessages(),
          onModelChange,
          onReasoningProfileChange,
          onKnowledgeFolderChange,
          onCancelEditingUserMessage,
          onChangeEditingUserMessage,
          onRemoveDraftAttachment: onRemoveAttachment,
          onRejectPendingMemory,
          onRefreshMessagePendingMemories: (messageId: number) => void onRefreshMessagePendingMemories(messageId),
          onRetry: onRetryAssistant,
          onStartEditingUserMessage,
          onSubmitEditingUserMessage: (messageId: number | string) => void onSubmitEditedUserMessage(messageId),
          onSelectAttachments,
          onNewDebate,
          onNewBattle,
          onSend: () => void onSend(),
          onStop,
          onToggleRecording,
          onToggleRag,
          onToggleWeb,
          toolMode,
          submitBlocked,
          submitBlockedReason,
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
              ? "debate"
              : null
            : activeConversationId !== null
              ? "chat"
              : null
          : null,
      activeItemTitle: activeDebate?.topic ?? activeConversation?.title ?? "",
      isDesktop,
      mobileModel: showChatModelSelector ? selectedModel : "",
      mobileModels: showChatModelSelector ? availableModels : [],
      onDeleteItem: async (itemId: number, kind: "chat" | "debate") => {
        if (kind === "debate") {
          await onDeleteDebate(itemId);
          return;
        }
        await onDeleteConversation(itemId);
      },
      onExportItem,
      onRenameItem,
      onMobileModelChange: showChatModelSelector ? onModelChange : undefined,
      onToggleSidebar,
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
      knowledgeFolders,
      knowledgeFolder,
      onAnimationComplete: options.onAnimationComplete,
      onChangeDraft,
      onComposerModeChange: onChangeComposerMode,
      onModelChange,
      onReasoningProfileChange,
      onKnowledgeFolderChange,
      onRemoveDraftAttachment: onRemoveAttachment,
      onSelectAttachments,
      onNewDebate,
      onNewBattle,
      onSend: () => void onSend(),
      onStop,
      onToggleRecording,
      onToggleRag,
      onToggleWeb,
      toolMode,
      submitBlocked,
      submitBlockedReason,
      shouldAnimate: !landingHeroAnimated,
      title: landingTitle,
    },
    imageSettingsProps: {
      imageSize,
      imageQuality,
      imageOutputFormat,
      onImageSizeChange: onChangeImageSize,
      onImageQualityChange: onChangeImageQuality,
      onImageOutputFormatChange: onChangeImageOutputFormat,
    },
    generalSettingsProps: {
      availableModels,
      defaultModel: generalPreferences.defaultModel,
      temperature: generalPreferences.temperature,
      onDefaultModelChange: onChangeDefaultModel,
      onTemperatureChange: (temperature: number) => onChangeGeneralPreferences({ temperature }),
    },
    memorySettingsProps: {
      isSaving: memoryManager.isSaving,
      settings: memoryManager.settings,
      onChangeSettings: memoryManager.onChangeSettings,
      onClearChatHistoryIndex: memoryManager.onClearChatHistoryIndex,
      onClearSavedMemories: memoryManager.onClearSavedMemories,
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
      onSelectModel: onModelChange,
      selectedModel,
    },
    isBattleLoading,
    isConversationLoading,
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
      onSelectSection,
      onDelete: onDeleteConversation,
      onDeleteDebate,
      onDeleteBattle,
      onNewChat,
      onNewDebate,
      onQueryChange: onChangeQuery,
      onRename: onRenameConversation,
      onRenameDebate,
      onRenameBattle,
      onSelect: onSelectConversation,
      onSelectDebate,
      onSelectBattle,
      onToggleSidebar,
      open: sidebarOpen,
      query,
    },
  };
}
