import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from "react";

import { ApiError } from "../../../shared/api/http";
import { useLatestRequestGuard } from "../../../shared/hooks/useLatestRequestGuard";
import {
  deleteConversation,
  fetchConversation,
  fetchConversationMessages,
  fetchConversations,
  renameConversation,
} from "../api/conversations";
import { streamActiveChat } from "../api/streamChat";
import { ASSISTANT_DRAFT_ID } from "../lib/constants";
import { mergeConversationWithCache } from "../lib/chatSessionUtils";
import { saveConversationSummariesCache } from "../../workspace/model/workspaceCache";
import type { ConversationDetail, ConversationSummary } from "../../../types";

const CONVERSATION_VIEW_MESSAGE_LIMIT = 24;
const CONVERSATION_EXPORT_MESSAGE_LIMIT = 100;
const ACTIVE_CHAT_CONVERSATION_CACHE_STORAGE_KEY = "chatchat.active-chat-conversations";

function loadStoredChatConversationCache(): Record<number, ConversationDetail> {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    const raw = window.sessionStorage.getItem(ACTIVE_CHAT_CONVERSATION_CACHE_STORAGE_KEY);
    if (!raw) {
      return {};
    }

    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      return {};
    }

    const next: Record<number, ConversationDetail> = {};
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      const conversationId = Number(key);
      if (!Number.isInteger(conversationId) || !value || typeof value !== "object") {
        continue;
      }

      const candidate = value as Partial<ConversationDetail>;
      if (
        typeof candidate.id !== "number"
        || candidate.id !== conversationId
        || typeof candidate.title !== "string"
        || typeof candidate.model !== "string"
        || !Array.isArray(candidate.messages)
      ) {
        continue;
      }

      next[conversationId] = candidate as ConversationDetail;
    }

    return next;
  } catch {
    return {};
  }
}

interface UseChatConversationLifecycleOptions {
  abortAndRemoveSession: (conversationId: number) => void;
  activeConversation: ConversationDetail | null;
  activeConversationId: number | null;
  activeSession: { status: string; conversation: ConversationDetail } | null | undefined;
  attachActiveStream: (options: {
    conversation: ConversationDetail;
    errorMessage: string;
    request: (handlers: {
      onEvent: (event: any) => void;
      signal: AbortSignal;
    }) => Promise<void>;
  }) => Promise<unknown>;
  cancelRecording: () => void;
  clearAttachments: () => void;
  conversations: ConversationSummary[];
  deferredQuery: string;
  getSessionConversation: (conversationId: number) => ConversationDetail | null;
  mergeConversationSummariesWithSessions: (items: ConversationSummary[]) => ConversationSummary[];
  renameSession: (conversationId: number, title: string) => void;
  runningSessions: Array<{ conversation: ConversationDetail }>;
  setActiveConversation: Dispatch<SetStateAction<ConversationDetail | null>>;
  setActiveConversationId: Dispatch<SetStateAction<number | null>>;
  setCollapsedMessageIds: Dispatch<SetStateAction<Set<number | string>>>;
  setConversations: Dispatch<SetStateAction<ConversationSummary[]>>;
  setConversationsLoaded: Dispatch<SetStateAction<boolean>>;
  setDraft: Dispatch<SetStateAction<string>>;
  setEditingUserMessageContent: Dispatch<SetStateAction<string>>;
  setEditingUserMessageId: Dispatch<SetStateAction<number | string | null>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSelectedModel: Dispatch<SetStateAction<string>>;
}

export function useChatConversationLifecycle({
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
}: UseChatConversationLifecycleOptions) {
  const [earlierMessagesError, setEarlierMessagesError] = useState<string | null>(null);
  const [isLoadingEarlierMessages, setIsLoadingEarlierMessages] = useState(false);
  const chatConversationCacheRef = useRef<Record<number, ConversationDetail>>(
    loadStoredChatConversationCache(),
  );
  const conversationLoadAbortRef = useRef<AbortController | null>(null);
  const earlierMessagesAbortRef = useRef<AbortController | null>(null);
  const conversationLoadGuard = useLatestRequestGuard();
  const conversationsRefreshGuard = useLatestRequestGuard();

  const writeChatConversationCache = useCallback((cache: Record<number, ConversationDetail>) => {
    chatConversationCacheRef.current = cache;
    if (typeof window === "undefined") {
      return;
    }

    try {
      if (Object.keys(cache).length === 0) {
        window.sessionStorage.removeItem(ACTIVE_CHAT_CONVERSATION_CACHE_STORAGE_KEY);
        return;
      }

      window.sessionStorage.setItem(
        ACTIVE_CHAT_CONVERSATION_CACHE_STORAGE_KEY,
        JSON.stringify(cache),
      );
    } catch {
      // 会话流式缓存失败时，内存里的草稿仍然能保持页面可用。
    }
  }, []);

  const upsertChatConversationCache = useCallback(
    (conversation: ConversationDetail) => {
      if (conversation.id <= 0) {
        return;
      }

      writeChatConversationCache({
        ...chatConversationCacheRef.current,
        [conversation.id]: conversation,
      });
    },
    [writeChatConversationCache],
  );

  const removeChatConversationCache = useCallback(
    (conversationId: number) => {
      if (!(conversationId in chatConversationCacheRef.current)) {
        return;
      }

      const { [conversationId]: _removed, ...rest } = chatConversationCacheRef.current;
      writeChatConversationCache(rest);
    },
    [writeChatConversationCache],
  );

  useEffect(() => {
    runningSessions.forEach((session) => {
      if (session.conversation.id > 0) {
        upsertChatConversationCache(session.conversation);
      }
    });
  }, [runningSessions, upsertChatConversationCache]);

  useEffect(() => {
    setEditingUserMessageId(null);
    setEditingUserMessageContent("");
    setEarlierMessagesError(null);
  }, [activeConversationId, setEditingUserMessageContent, setEditingUserMessageId]);

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
      const cachedConversation = chatConversationCacheRef.current[conversationId] ?? null;
      if (cachedConversation) {
        setActiveConversation(cachedConversation);
        setSelectedModel(cachedConversation.model);
      }

      try {
        const serverConversation = await fetchConversation(conversationId, {
          limit: CONVERSATION_VIEW_MESSAGE_LIMIT,
          signal: controller.signal,
        });
        if (!conversationLoadGuard.isCurrent(requestId)) {
          return;
        }
        const conversation = mergeConversationWithCache(serverConversation, cachedConversation);
        setActiveConversation(conversation);
        setSelectedModel(conversation.model);
        if (!serverConversation.active_run) {
          removeChatConversationCache(conversationId);
        }
        if (serverConversation.active_run) {
          void attachActiveStream({
            conversation,
            errorMessage: "Failed to reconnect active response.",
            request: async ({ onEvent, signal }) => {
              try {
                await streamActiveChat(conversation.id, {
                  onEvent,
                  runId: conversation.active_run?.run_id ?? null,
                  afterSeq: conversation.active_run?.last_seq ?? null,
                  signal,
                });
              } catch (error) {
                if (!(error instanceof ApiError) || (error.status !== 404 && error.status !== 409)) {
                  throw error;
                }

                const refreshed = mergeConversationWithCache(
                  await fetchConversation(conversation.id, {
                    limit: CONVERSATION_VIEW_MESSAGE_LIMIT,
                    signal,
                  }),
                  chatConversationCacheRef.current[conversation.id],
                );
                removeChatConversationCache(conversation.id);
                const lastAssistant = [...refreshed.messages]
                  .reverse()
                  .find((message) => message.role === "assistant");

                if (lastAssistant?.reasoning) {
                  onEvent({ type: "reasoning", content: lastAssistant.reasoning });
                }
                if (lastAssistant?.sources?.length) {
                  onEvent({ type: "sources", sources: lastAssistant.sources });
                }
                if (lastAssistant?.context) {
                  onEvent({ type: "context", context: lastAssistant.context });
                }
                onEvent({
                  type: "done",
                  assistant_message_id: typeof lastAssistant?.id === "number" ? lastAssistant.id : undefined,
                  conversation_title: refreshed.title,
                  content: lastAssistant?.content ?? "",
                });
              }
            },
          });
        }
      } catch (loadError) {
        if (controller.signal.aborted || !conversationLoadGuard.isCurrent(requestId)) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Failed to load conversation.");
      } finally {
        if (conversationLoadAbortRef.current === controller) {
          conversationLoadAbortRef.current = null;
        }
      }
    },
    [
      attachActiveStream,
      conversationLoadGuard,
      getSessionConversation,
      removeChatConversationCache,
      setActiveConversation,
      setError,
      setSelectedModel,
    ],
  );

  useEffect(() => {
    if (!activeConversation || activeConversation.id <= 0) {
      return;
    }

    if (activeSession?.status === "running") {
      upsertChatConversationCache(activeSession.conversation);
      return;
    }

    if (activeConversation.messages.some((message) => message.id === ASSISTANT_DRAFT_ID)) {
      upsertChatConversationCache(activeConversation);
      return;
    }

    removeChatConversationCache(activeConversation.id);
  }, [
    activeConversation,
    activeSession,
    removeChatConversationCache,
    upsertChatConversationCache,
  ]);

  const filteredConversations = conversations.filter((item) => {
    if (!deferredQuery.trim()) {
      return true;
    }
    return item.title.toLowerCase().includes(deferredQuery.toLowerCase());
  });

  const refreshConversations = useCallback(async () => {
    const requestId = conversationsRefreshGuard.begin();
    try {
      const items = await fetchConversations();
      if (!conversationsRefreshGuard.isCurrent(requestId)) {
        return;
      }
      saveConversationSummariesCache(items);
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
  }, [
    conversationsRefreshGuard,
    mergeConversationSummariesWithSessions,
    setConversations,
    setConversationsLoaded,
    setError,
  ]);

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    if (activeConversationId !== null) {
      void loadConversation(activeConversationId);
    }
  }, [activeConversationId, loadConversation]);

  const handleRenameConversation = useCallback(
    async (conversationId: number, title: string) => {
      await renameConversation(conversationId, title);
      setActiveConversation((current) =>
        current && current.id === conversationId ? { ...current, title } : current,
      );
      renameSession(conversationId, title);
      await refreshConversations();
    },
    [refreshConversations, renameSession, setActiveConversation],
  );

  const handleDeleteConversation = useCallback(
    async (conversationId: number) => {
      try {
        cancelRecording();
        abortAndRemoveSession(conversationId);
        removeChatConversationCache(conversationId);
        await deleteConversation(conversationId);
        await refreshConversations();

        if (activeConversationId === conversationId) {
          setActiveConversationId(null);
          setActiveConversation(null);
          setCollapsedMessageIds(new Set());
          setDraft("");
          clearAttachments();
        }
      } catch (deleteError) {
        setError(deleteError instanceof Error ? deleteError.message : "Failed to delete conversation.");
      }
    },
    [
      abortAndRemoveSession,
      activeConversationId,
      cancelRecording,
      clearAttachments,
      refreshConversations,
      removeChatConversationCache,
      setActiveConversation,
      setActiveConversationId,
      setCollapsedMessageIds,
      setDraft,
      setError,
    ],
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
    setEarlierMessagesError(null);

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
      if (!controller.signal.aborted) {
        setEarlierMessagesError(
          loadError instanceof Error ? loadError.message : "Failed to load earlier messages.",
        );
      }
    } finally {
      if (earlierMessagesAbortRef.current === controller) {
        earlierMessagesAbortRef.current = null;
      }
      setIsLoadingEarlierMessages(false);
    }
  }, [activeConversation, isLoadingEarlierMessages, setActiveConversation]);

  const loadFullConversationForExport = useCallback(async (conversationId: number) => {
    let conversation = await fetchConversation(conversationId, {
      limit: CONVERSATION_EXPORT_MESSAGE_LIMIT,
    });

    while (conversation.remaining_message_count > 0) {
      const firstPersistedMessage = conversation.messages.find(
        (message) => typeof message.id === "number",
      );
      if (!firstPersistedMessage || typeof firstPersistedMessage.id !== "number") {
        break;
      }

      const page = await fetchConversationMessages(conversationId, {
        beforeMessageId: firstPersistedMessage.id,
        limit: CONVERSATION_EXPORT_MESSAGE_LIMIT,
      });

      conversation = {
        ...conversation,
        messages: [...page.messages, ...conversation.messages],
        loaded_message_count: conversation.loaded_message_count + page.loaded_message_count,
        remaining_message_count: page.remaining_message_count,
      };
    }

    return conversation;
  }, []);

  return {
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
  };
}
