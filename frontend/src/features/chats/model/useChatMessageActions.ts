import {
  useCallback,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from "react";

import { pollImageGenerationJob } from "../api/generateImage";
import { regenerateChat, streamChat } from "../api/streamChat";
import {
  confirmPendingMemory,
  fetchMessagePendingMemories,
  rejectPendingMemory,
  updateMessageFeedback,
} from "../api/conversations";
import { ASSISTANT_DRAFT_ID, deriveConversationTitle } from "../lib/constants";
import {
  appendRetryDraft,
  createAssistantDraftMessageForModel,
  createTransientAttachments,
  createUserDraftMessage,
  removePendingMemory,
  restoreAttachmentFiles,
  setMessagePendingMemories,
  stageForToolMode,
  type RunStreamOptions,
} from "../lib/chatSessionUtils";
import type { RunStreamResult } from "./useConversationStreams";
import {
  resolveImageGenerationOutputFormat,
  resolveImageGenerationQuality,
  resolveImageGenerationSize,
} from "../lib/imageSizeOptions";
import type { PetSignalType } from "../../pet/model/petSignals";
import type {
  ChatMessage,
  ComposerMode,
  ConversationDetail,
  MemoryCandidateUpdatePayload,
  ReasoningProfileValue,
  ToolMode,
} from "../../../types";

const IMAGE_ATTACHMENT_EXTENSIONS = new Set([".gif", ".jpeg", ".jpg", ".png", ".webp"]);

function fileExtension(name: string) {
  const dotIndex = name.lastIndexOf(".");
  return dotIndex >= 0 ? name.slice(dotIndex).toLowerCase() : "";
}

function fileLooksLikeImage(file: File) {
  return file.type.startsWith("image/") || IMAGE_ATTACHMENT_EXTENSIONS.has(fileExtension(file.name));
}

function findNextAssistantMessage(messages: ChatMessage[], startIndex: number): ChatMessage | null {
  for (let index = startIndex + 1; index < messages.length; index += 1) {
    const candidate = messages[index];
    if (candidate.role === "assistant") {
      return candidate;
    }
    if (candidate.role === "user") {
      break;
    }
  }

  return null;
}

type StopStream = (options: {
  conversationId: number;
  restoreAttachments: (files: File[]) => void;
  restoreDraft: (content: string) => void;
  getCurrentDraft: () => string;
}) => Promise<void>;

interface UseChatMessageActionsOptions {
  activeConversation: ConversationDetail | null;
  activeKnowledgeFolders: string[];
  activeReasoningRequest: ReasoningProfileValue | null;
  chatModelBeforeImageRef: MutableRefObject<string>;
  clearAttachments: () => void;
  composerModeRef: MutableRefObject<ComposerMode>;
  draft: string;
  draftAttachments: Array<{ file: File }>;
  editingUserMessageContent: string;
  imageOutputFormat: string;
  imageQuality: string;
  imageSize: string;
  imageUploadAvailable: boolean;
  isRecording: boolean;
  isStreaming: boolean;
  isTranscribing: boolean;
  onModelLoveScoreChange?: (modelId: string, delta: number) => void;
  onModelUsageCountChange?: (modelId: string, delta: number) => void;
  onPetEvent?: (type: PetSignalType) => void;
  projectId?: number | null;
  refreshConversations: () => Promise<void>;
  replaceAttachments: (files: File[]) => void;
  restoreChatComposerMode: () => void;
  runStream: (options: RunStreamOptions) => Promise<RunStreamResult>;
  selectedModel: string;
  setActiveConversation: Dispatch<SetStateAction<ConversationDetail | null>>;
  setActiveConversationId: Dispatch<SetStateAction<number | null>>;
  setCollapsedMessageIds: Dispatch<SetStateAction<Set<number | string>>>;
  setDraft: Dispatch<SetStateAction<string>>;
  setEditingUserMessageContent: Dispatch<SetStateAction<string>>;
  setEditingUserMessageId: Dispatch<SetStateAction<number | string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  stopStream: StopStream;
  temperature: number;
  toolMode: ToolMode;
  transientAttachmentUrlsRef: MutableRefObject<string[]>;
}

export function useChatMessageActions({
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
  onModelLoveScoreChange,
  onModelUsageCountChange,
  onPetEvent,
  projectId,
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
  temperature,
  toolMode,
  transientAttachmentUrlsRef,
}: UseChatMessageActionsOptions) {
  const handleSend = useCallback(async () => {
    const message = draft.trim();
    const pendingFiles = draftAttachments.map((attachment) => attachment.file);
    const effectiveComposerMode = composerModeRef.current;
    if ((!message && pendingFiles.length === 0) || isRecording || isStreaming || isTranscribing) {
      return;
    }
    if (!imageUploadAvailable && pendingFiles.some(fileLooksLikeImage)) {
      setError("当前模型不支持图片上传，请切换到 Claude/Gemini/Codex 等多模态模型。");
      return;
    }
    if (effectiveComposerMode === "image") {
      if (!message || pendingFiles.length > 0 || !selectedModel) {
        return;
      }

      const conversationModel = activeConversation?.model ?? selectedModel;
      const imageGenerationSize = resolveImageGenerationSize(imageSize);
      const imageGenerationQuality = resolveImageGenerationQuality(imageQuality);
      const imageGenerationOutputFormat = resolveImageGenerationOutputFormat(imageOutputFormat);
      const tempConversationId =
        activeConversation?.id != null ? activeConversation.id : -Date.now();
      const tempUserMessageId = `user-${Date.now()}`;
      const tempUserMessage = createUserDraftMessage(tempUserMessageId, message, []);
      const nextConversation: ConversationDetail = activeConversation
        ? {
            ...activeConversation,
            model: conversationModel,
            total_message_count: activeConversation.total_message_count + 2,
            loaded_message_count: activeConversation.loaded_message_count + 2,
            messages: [
              ...activeConversation.messages,
              tempUserMessage,
              createAssistantDraftMessageForModel(conversationModel),
            ],
          }
        : {
            id: tempConversationId,
            project_id: projectId ?? null,
            title: deriveConversationTitle(message, 0),
            model: conversationModel,
            total_message_count: 2,
            loaded_message_count: 2,
            remaining_message_count: 0,
            messages: [tempUserMessage, createAssistantDraftMessageForModel(conversationModel)],
          };

      // 真正接受发送后再通知宠物，避免空消息/被拦截提交也触发动作。
      onPetEvent?.("send");
      setDraft("");
      clearAttachments();
      restoreChatComposerMode();
      setActiveConversationId(tempConversationId);
      setActiveConversation(nextConversation);

      const result = await runStream({
        conversation: nextConversation,
        errorMessage: "Failed to generate image.",
        initialStage: "generating_image",
        restoreInput: {
          content: message,
          loadFiles: async () => [],
        },
        tempUserMessageId,
        request: ({ onEvent, signal }) =>
          pollImageGenerationJob(
            {
              conversation_id:
                activeConversation && activeConversation.id > 0 ? activeConversation.id : null,
              project_id: activeConversation && activeConversation.id > 0 ? activeConversation.project_id : projectId,
              prompt: message,
              size: imageGenerationSize,
              quality: imageGenerationQuality,
              output_format: imageGenerationOutputFormat,
            },
            { model: conversationModel, onEvent, signal },
          ),
      });

      if (result === "completed") {
        onPetEvent?.("complete");
        await refreshConversations();
      }
      return;
    }

    const effectiveModel = selectedModel;
    const effectiveReasoningProfile = activeReasoningRequest;
    const tempConversationId =
      activeConversation?.id != null ? activeConversation.id : -Date.now();
    const initialStage =
      pendingFiles.length > 0 ? "analyzing_attachments" : (stageForToolMode(toolMode) ?? "waiting_for_model");
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
          messages: [...activeConversation.messages, tempUserMessage, createAssistantDraftMessageForModel(effectiveModel)],
        }
      : {
          id: tempConversationId,
          project_id: projectId ?? null,
          title: deriveConversationTitle(message, tempAttachments.length),
          model: effectiveModel,
          total_message_count: 2,
          loaded_message_count: 2,
          remaining_message_count: 0,
          messages: [tempUserMessage, createAssistantDraftMessageForModel(effectiveModel)],
        };

    // 真正接受发送后再通知宠物，避免空消息/被拦截提交也触发动作。
    onPetEvent?.("send");
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
            project_id: activeConversation && activeConversation.id > 0 ? activeConversation.project_id : projectId,
            message,
            files: pendingFiles,
            model: effectiveModel,
            temperature,
            reasoning_profile: effectiveReasoningProfile,
            tool_mode: toolMode,
            knowledge_folders: activeKnowledgeFolders,
          },
          { onEvent, signal },
        ),
    });

    if (result === "completed") {
      onModelUsageCountChange?.(effectiveModel, 1);
      onPetEvent?.("complete");
      await refreshConversations();
    }
  }, [
    activeConversation,
    activeKnowledgeFolders,
    activeReasoningRequest,
    chatModelBeforeImageRef,
    clearAttachments,
    composerModeRef,
    draft,
    draftAttachments,
    imageOutputFormat,
    imageQuality,
    imageSize,
    imageUploadAvailable,
    isRecording,
    isStreaming,
    isTranscribing,
    onModelUsageCountChange,
    onPetEvent,
    projectId,
    refreshConversations,
    restoreChatComposerMode,
    runStream,
    selectedModel,
    setActiveConversation,
    setActiveConversationId,
    setDraft,
    setError,
    temperature,
    toolMode,
    transientAttachmentUrlsRef,
  ]);

  const handleStop = useCallback(async () => {
    if (!activeConversation) {
      return;
    }

    await stopStream({
      conversationId: activeConversation.id,
      restoreAttachments: replaceAttachments,
      restoreDraft: setDraft,
      getCurrentDraft: () => draft,
    });
  }, [activeConversation, draft, replaceAttachments, setDraft, stopStream]);

  const startRegeneratedBranch = useCallback(
    async ({
      content,
      errorMessage,
      restoreToComposerOnStop = true,
      sourceAssistantId,
      sourceUser,
    }: {
      content: string;
      errorMessage: string;
      restoreToComposerOnStop?: boolean;
      sourceAssistantId: number | string | null;
      sourceUser: ChatMessage;
    }) => {
      if (!activeConversation || isStreaming) {
        return;
      }

      const nextContent = content.trim();
      if (!nextContent) {
        return;
      }

      const effectiveModel = selectedModel;
      const effectiveReasoningProfile = activeReasoningRequest;
      const retryUserDraftId = `retry-user-${sourceUser.id}-${Date.now()}`;
      const nextConversation = appendRetryDraft(
        activeConversation,
        retryUserDraftId,
        nextContent,
        effectiveModel,
        sourceUser.attachments ?? [],
      );
      const retryConversation: ConversationDetail = {
        ...nextConversation,
        total_message_count: nextConversation.total_message_count + 2,
        loaded_message_count: nextConversation.loaded_message_count + 2,
      };
      const collapsedIds = sourceAssistantId == null ? [sourceUser.id] : [sourceUser.id, sourceAssistantId];

      setCollapsedMessageIds((current) => new Set([...current, ...collapsedIds]));
      setActiveConversation(retryConversation);

      const result = await runStream({
        conversation: retryConversation,
        errorMessage,
        initialStage: stageForToolMode(toolMode) ?? "waiting_for_model",
        restoreInput: {
          content: nextContent,
          loadFiles: () => restoreAttachmentFiles(sourceUser.attachments ?? []),
          restoreToComposerOnStop,
        },
        tempUserMessageId: retryUserDraftId,
        request: async ({ onEvent, signal }) => {
          if (typeof sourceAssistantId === "number") {
            return regenerateChat(
              {
                conversation_id: activeConversation.id,
                assistant_message_id: sourceAssistantId,
                edited_content: nextContent,
                model: effectiveModel,
                temperature,
                reasoning_profile: effectiveReasoningProfile,
                tool_mode: toolMode,
                knowledge_folders: activeKnowledgeFolders,
              },
              { onEvent, signal },
            );
          }

          const restoredFiles = await restoreAttachmentFiles(sourceUser.attachments ?? []);
          return streamChat(
            {
              conversation_id: activeConversation.id > 0 ? activeConversation.id : null,
              project_id: activeConversation.project_id ?? projectId,
              message: nextContent,
              files: restoredFiles,
              model: effectiveModel,
              temperature,
              reasoning_profile: effectiveReasoningProfile,
              tool_mode: toolMode,
              knowledge_folders: activeKnowledgeFolders,
            },
            { onEvent, signal },
          );
        },
      });

      if (result === "completed") {
        onModelUsageCountChange?.(effectiveModel, 1);
        await refreshConversations();
      }
    },
    [
      activeConversation,
      activeKnowledgeFolders,
      activeReasoningRequest,
      isStreaming,
      onModelUsageCountChange,
      projectId,
      refreshConversations,
      runStream,
      selectedModel,
      setActiveConversation,
      setCollapsedMessageIds,
      temperature,
      toolMode,
    ],
  );

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

      await startRegeneratedBranch({
        content: sourceUser.content,
        errorMessage: "Failed to regenerate response.",
        sourceAssistantId: messageId,
        sourceUser,
      });
    },
    [activeConversation, isStreaming, startRegeneratedBranch],
  );

  const handleStartEditingUserMessage = useCallback(
    (messageId: number | string) => {
      if (!activeConversation || isStreaming) {
        return;
      }

      const targetMessage = activeConversation.messages.find(
        (item) => item.id === messageId && item.role === "user",
      );
      if (!targetMessage) {
        return;
      }

      setEditingUserMessageId(messageId);
      setEditingUserMessageContent(targetMessage.content);
    },
    [activeConversation, isStreaming, setEditingUserMessageContent, setEditingUserMessageId],
  );

  const handleCancelEditingUserMessage = useCallback(() => {
    setEditingUserMessageId(null);
    setEditingUserMessageContent("");
  }, [setEditingUserMessageContent, setEditingUserMessageId]);

  const handleSubmitEditedUserMessage = useCallback(
    async (messageId: number | string) => {
      if (!activeConversation || isStreaming) {
        return;
      }

      const targetIndex = activeConversation.messages.findIndex(
        (item) => item.id === messageId && item.role === "user",
      );
      if (targetIndex < 0) {
        return;
      }

      const sourceUser = activeConversation.messages[targetIndex];
      const sourceAssistant = findNextAssistantMessage(activeConversation.messages, targetIndex);
      if (!sourceAssistant && targetIndex !== activeConversation.messages.length - 1) {
        return;
      }

      const nextContent = editingUserMessageContent.trim();
      if (!nextContent) {
        return;
      }

      setEditingUserMessageId(null);
      setEditingUserMessageContent("");

      await startRegeneratedBranch({
        content: nextContent,
        errorMessage: "Failed to regenerate response.",
        restoreToComposerOnStop: false,
        sourceAssistantId: sourceAssistant?.id ?? null,
        sourceUser,
      });
    },
    [
      activeConversation,
      editingUserMessageContent,
      isStreaming,
      setEditingUserMessageContent,
      setEditingUserMessageId,
      startRegeneratedBranch,
    ],
  );

  const handleMessageFeedback = useCallback(async (messageId: number, value: "up" | "down" | null) => {
    const targetMessage = activeConversation?.messages.find((message) => message.id === messageId);
    const previousValue = targetMessage?.feedback ?? null;
    const modelId = (targetMessage?.model || activeConversation?.model || "").trim();
    const feedbackWeight = (feedback: "up" | "down" | null) => {
      if (feedback === "up") {
        return 1;
      }
      if (feedback === "down") {
        return -1;
      }
      return 0;
    };

    try {
      await updateMessageFeedback(messageId, value);
      const delta = feedbackWeight(value) - feedbackWeight(previousValue);
      if (modelId && delta !== 0) {
        onModelLoveScoreChange?.(modelId, delta);
      }
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
  }, [activeConversation, onModelLoveScoreChange, setActiveConversation, setError]);

  const handleRefreshMessagePendingMemories = useCallback(async (messageId: number) => {
    try {
      const pendingMemories = await fetchMessagePendingMemories(messageId);
      setActiveConversation((current) =>
        current ? setMessagePendingMemories(current, messageId, pendingMemories) : current,
      );
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load pending memories.");
    }
  }, [setActiveConversation, setError]);

  const handleConfirmPendingMemory = useCallback(
    async (memoryId: number, payload?: MemoryCandidateUpdatePayload) => {
      try {
        await confirmPendingMemory(memoryId, payload);
        setActiveConversation((current) => (current ? removePendingMemory(current, memoryId) : current));
      } catch (saveError) {
        setError(saveError instanceof Error ? saveError.message : "Failed to confirm pending memory.");
      }
    },
    [setActiveConversation, setError],
  );

  const handleRejectPendingMemory = useCallback(
    async (memoryId: number) => {
      try {
        await rejectPendingMemory(memoryId);
        setActiveConversation((current) => (current ? removePendingMemory(current, memoryId) : current));
      } catch (saveError) {
        setError(saveError instanceof Error ? saveError.message : "Failed to reject pending memory.");
      }
    },
    [setActiveConversation, setError],
  );

  return {
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
  };
}
