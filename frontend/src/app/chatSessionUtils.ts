import { toApiUrl } from "../lib/api";
import type {
  ChatMessage,
  ChatStreamEvent,
  ConversationDetail,
  ConversationSummary,
  MessageContext,
  MessageAttachment,
  ToolMode,
} from "../types";
import { ASSISTANT_DRAFT_ID } from "./constants";

export type ConversationUpdater = (current: ConversationDetail) => ConversationDetail;

export type RestoreInput = {
  content: string;
  loadFiles: () => Promise<File[]>;
  restoreToComposerOnStop?: boolean;
};

export type RunStreamOptions = {
  errorMessage: string;
  conversation: ConversationDetail;
  initialStage: StreamingStage | null;
  restoreInput: RestoreInput;
  tempUserMessageId: number | string;
  request: (handlers: {
    onEvent: (event: ChatStreamEvent) => void;
    signal: AbortSignal;
  }) => Promise<void>;
};

export type StreamingStage =
  | "waiting_for_model"
  | "analyzing_attachments"
  | "reading_notes"
  | "reading_files"
  | "searching";

export type StreamSessionStatus = "running" | "completed" | "stopped" | "error";

export type StreamSession = {
  conversation: ConversationDetail;
  pendingContext?: MessageContext | null;
  reasoning: string;
  reasoningStreaming: boolean;
  restoreInput: RestoreInput;
  stage: StreamingStage | null;
  stageStartedAt: number;
  status: StreamSessionStatus;
  unread: boolean;
};

export type ConversationActivity = {
  running: boolean;
  unread: boolean;
};

export function stageFromStatusItems(items: string[]): StreamingStage | null {
  const normalizedItems = new Set(items);
  if (normalizedItems.has("Waiting for model")) {
    return "waiting_for_model";
  }
  if (
    normalizedItems.has("Reading image")
    || normalizedItems.has("Reading attachments")
    || normalizedItems.has("Analyzing attachments")
  ) {
    return "analyzing_attachments";
  }
  if (normalizedItems.has("Reading notes")) {
    return "reading_notes";
  }
  if (normalizedItems.has("Reading files")) {
    return "reading_files";
  }
  if (normalizedItems.has("Searching")) {
    return "searching";
  }
  return null;
}

export function stageForToolMode(mode: ToolMode): StreamingStage | null {
  if (mode === "knowledge") {
    return "reading_notes";
  }
  if (mode === "search") {
    return "searching";
  }
  return null;
}

export function labelForStage(stage: StreamingStage | null): string | null {
  if (stage === "waiting_for_model") {
    return "正在组织回答";
  }
  if (stage === "analyzing_attachments") {
    return "分析附件";
  }
  if (stage === "reading_notes") {
    return "阅读知识库";
  }
  if (stage === "reading_files") {
    return "阅读文件";
  }
  if (stage === "searching") {
    return "联网搜索";
  }
  return null;
}

export function streamSessionKey(conversationId: number) {
  return String(conversationId);
}

function normalizePreviewText(content: string) {
  return content.replace(/\s+/g, " ").trim();
}

function conversationPreview(conversation: ConversationDetail) {
  const lastMessage = [...conversation.messages].reverse().find((item) => item.role !== "system");
  if (!lastMessage) {
    return "";
  }

  const content = normalizePreviewText(lastMessage.content);
  if (content) {
    return content;
  }

  if (lastMessage.localStatus === "stopped") {
    return "You stopped this response";
  }

  const firstAttachment = lastMessage.attachments?.[0];
  if (!firstAttachment) {
    return "";
  }

  return lastMessage.attachments?.length === 1
    ? firstAttachment.original_name
    : `${lastMessage.attachments?.length ?? 0} attachments`;
}

export function toConversationSummary(conversation: ConversationDetail): ConversationSummary {
  return {
    id: conversation.id,
    title: conversation.title,
    model: conversation.model,
    updated_at: new Date().toISOString(),
    last_message_preview: conversationPreview(conversation),
  };
}

export function sortConversations(items: ConversationSummary[]) {
  return [...items].sort((left, right) => {
    const leftTime = left.updated_at ? Date.parse(left.updated_at) : 0;
    const rightTime = right.updated_at ? Date.parse(right.updated_at) : 0;
    return rightTime - leftTime;
  });
}

export function mergeConversationSummaries(
  items: ConversationSummary[],
  sessions: Record<string, StreamSession>,
) {
  const byId = new Map(items.map((item) => [item.id, item]));
  Object.values(sessions).forEach((session) => {
    if (session.conversation.id > 0) {
      byId.set(session.conversation.id, toConversationSummary(session.conversation));
    }
  });
  return sortConversations([...byId.values()]);
}

export function createAssistantDraftMessageForModel(model: string): ChatMessage {
  return {
    id: ASSISTANT_DRAFT_ID,
    clientKey: createClientId("assistant"),
    role: "assistant",
    content: "",
    model,
  };
}

export function createUserDraftMessage(
  id: number | string,
  content: string,
  attachments: MessageAttachment[] = [],
): ChatMessage {
  return {
    id,
    clientKey: createClientId("user"),
    role: "user",
    content,
    attachments,
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

export function createClientId(prefix?: string): string {
  const cryptoObject = globalThis.crypto;
  const randomPart =
    cryptoObject?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  return prefix ? `${prefix}-${randomPart}` : randomPart;
}

function createLocalAssistantMessageId(kind: "error" | "stopped") {
  return createClientId(kind);
}

export function appendAssistantDraftContent(
  conversation: ConversationDetail,
  content: string,
): ConversationDetail {
  return updateAssistantDraft(conversation, (message) => ({
    ...message,
    content: message.content + content,
  }));
}

export function appendAssistantDraftReasoning(
  conversation: ConversationDetail,
  reasoning: string,
): ConversationDetail {
  return updateAssistantDraft(conversation, (message) => ({
    ...message,
    reasoning: `${message.reasoning ?? ""}${reasoning}`,
  }));
}

export function setAssistantDraftSources(
  conversation: ConversationDetail,
  sources: ChatMessage["sources"],
): ConversationDetail {
  return updateAssistantDraft(conversation, (message) => ({
    ...message,
    sources,
  }));
}

export function setAssistantDraftContext(
  conversation: ConversationDetail,
  context: MessageContext,
): ConversationDetail {
  return updateAssistantDraft(conversation, (message) => ({
    ...message,
    context,
  }));
}

export function setAssistantDraftId(
  conversation: ConversationDetail,
  assistantMessageId?: number | string,
): ConversationDetail {
  if (assistantMessageId === undefined || assistantMessageId === null) {
    return conversation;
  }
  return {
    ...conversation,
    messages: conversation.messages.map((item) =>
      item.id === ASSISTANT_DRAFT_ID ? { ...item, id: assistantMessageId } : item,
    ),
  };
}

export function setAssistantDraftModel(
  conversation: ConversationDetail,
  model: string,
): ConversationDetail {
  return {
    ...conversation,
    messages: conversation.messages.map((item) =>
      item.id === ASSISTANT_DRAFT_ID ? { ...item, model } : item,
    ),
  };
}

export function setAssistantDraftFinalContent(
  conversation: ConversationDetail,
  content: string,
): ConversationDetail {
  return {
    ...conversation,
    messages: conversation.messages.map((item) =>
      item.id === ASSISTANT_DRAFT_ID
        ? {
            ...item,
            content,
          }
        : item,
    ),
  };
}

export function replaceConversationMessageId(
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

export function replaceAssistantDraftWithError(
  conversation: ConversationDetail,
  message: string,
): ConversationDetail {
  const messages = conversation.messages.filter((item) => item.id !== ASSISTANT_DRAFT_ID);
  return {
    ...conversation,
    messages: [
      ...messages,
      {
        id: createLocalAssistantMessageId("error"),
        role: "assistant",
        content: message,
        localStatus: "error",
      },
    ],
  };
}

export function markAssistantDraftStopped(conversation: ConversationDetail): ConversationDetail {
  return updateAssistantDraft(conversation, (message) => ({
    ...message,
    id: createLocalAssistantMessageId("stopped"),
    localStatus: "stopped",
  }));
}

export function appendRetryDraft(
  conversation: ConversationDetail,
  userMessageId: number | string,
  content: string,
  model: string,
  attachments: MessageAttachment[] = [],
): ConversationDetail {
  const messages = conversation.messages.filter((item) => item.id !== ASSISTANT_DRAFT_ID);
  return {
    ...conversation,
    messages: [
      ...messages,
      createUserDraftMessage(userMessageId, content, attachments),
      createAssistantDraftMessageForModel(model),
    ],
  };
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function toStreamErrorMessage(error: unknown, fallbackMessage: string) {
  if (error instanceof Error) {
    return error.message;
  }

  return fallbackMessage;
}

async function restoreAttachmentFile(attachment: MessageAttachment): Promise<File> {
  const response = await fetch(toApiUrl(attachment.url));
  if (!response.ok) {
    throw new Error(`Failed to restore attachment: ${attachment.original_name}`);
  }

  const blob = await response.blob();
  return new File([blob], attachment.original_name, {
    type: attachment.mime_type || blob.type || "application/octet-stream",
    lastModified: Date.now(),
  });
}

export async function restoreAttachmentFiles(attachments: MessageAttachment[]) {
  return Promise.all(attachments.map(restoreAttachmentFile));
}

export function createTransientAttachments(files: File[]): MessageAttachment[] {
  return files.map((file) => ({
    id: createClientId(),
    kind: file.type.startsWith("image/") ? "image" : "file",
    original_name: file.name,
    mime_type: file.type,
    size_bytes: file.size,
    extension: file.name.includes(".") ? file.name.slice(file.name.lastIndexOf(".")).toLowerCase() : "",
    url: URL.createObjectURL(file),
  }));
}
