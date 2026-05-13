import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";

import type { ChatStreamEvent, ConversationDetail, ConversationSummary } from "../../../types";
import { cancelActiveChat } from "../api/streamChat";
import { ASSISTANT_DRAFT_ID } from "../lib/constants";
import {
  appendAssistantDraftContent,
  appendAssistantDraftReasoning,
  ConversationActivity,
  ConversationUpdater,
  ensureAssistantDraftMessage,
  isAbortError,
  markAssistantDraftStopped,
  mergeConversationSummaries,
  replaceAssistantDraftWithError,
  replaceConversationMessageId,
  RunStreamOptions,
  setAssistantDraftId,
  setAssistantDraftModel,
  setAssistantDraftContext,
  setAssistantDraftFinalContent,
  setAssistantDraftSearchTrace,
  setAssistantDraftSources,
  sortConversations,
  stageFromStatusItems,
  StreamSession,
  StreamSessionStatus,
  streamSessionKey,
  StreamingStage,
  toConversationSummary,
  toStreamErrorMessage,
} from "../lib/chatSessionUtils";

const THINK_BLOCK_PATTERN = /<think>[\s\S]*?<\/think>/gi;
const EMPTY_THINK_TAGS_PATTERN = /^(?:\s*<think>\s*<\/think>\s*)+$/i;
const LOOSE_THINK_TAG_PATTERN = /<\/?think>/gi;
const THINK_CLOSE_TAG_PATTERN = /<\/think>/i;

function sanitizeTokenContent(content: string): string {
  const trimmed = content.trim();
  if (!trimmed) {
    return content;
  }
  if (EMPTY_THINK_TAGS_PATTERN.test(trimmed)) {
    return "";
  }
  return content.replace(THINK_BLOCK_PATTERN, "").replace(LOOSE_THINK_TAG_PATTERN, "");
}

function shouldCloseReasoningStream(session: StreamSession, rawContent: string, cleanContent: string): boolean {
  if (!session.reasoningStreaming) {
    return false;
  }

  if (THINK_CLOSE_TAG_PATTERN.test(rawContent)) {
    return true;
  }

  return session.reasoning.trim().length > 0 && cleanContent.trim().length > 0;
}

const MIN_STAGE_DISPLAY_MS: Partial<Record<StreamingStage, number>> = {
  analyzing_attachments: 720,
};

const EMPTY_MODEL_RESPONSE_MESSAGE = "模型没有返回内容，请重试或切换模型。";

function finalizeAssistantDraft(
  session: StreamSession,
  event: Extract<ChatStreamEvent, { type: "done" }>,
): ConversationDetail {
  const finalContent = typeof event.content === "string" ? event.content : null;
  const currentDraft = session.conversation.messages.find(
    (message) => message.id === ASSISTANT_DRAFT_ID,
  );
  const hasAnswerContent = Boolean((finalContent ?? currentDraft?.content ?? "").trim());
  if (!hasAnswerContent) {
    const conversationWithError = replaceAssistantDraftWithError(
      session.conversation,
      EMPTY_MODEL_RESPONSE_MESSAGE,
    );
    return {
      ...conversationWithError,
      title: event.conversation_title ?? conversationWithError.title,
      active_run: null,
    };
  }

  const conversationWithContent = finalContent
    ? setAssistantDraftFinalContent(session.conversation, finalContent)
    : session.conversation;
  const conversationWithContext = session.pendingContext
    ? setAssistantDraftContext(conversationWithContent, session.pendingContext)
    : conversationWithContent;
  const conversationWithMessageId = setAssistantDraftId(
    conversationWithContext,
    event.assistant_message_id,
  );

  return {
    ...conversationWithMessageId,
    title: event.conversation_title ?? conversationWithMessageId.title,
    active_run: null,
  };
}

type UseConversationStreamsOptions = {
  activeConversation: ConversationDetail | null;
  activeConversationId: number | null;
  setActiveConversation: Dispatch<SetStateAction<ConversationDetail | null>>;
  setActiveConversationId: Dispatch<SetStateAction<number | null>>;
  setConversations: Dispatch<SetStateAction<ConversationSummary[]>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSelectedModel: Dispatch<SetStateAction<string>>;
};

type StopStreamOptions = {
  conversationId: number;
  restoreAttachments: (files: File[]) => void;
  restoreDraft: (content: string) => void;
  getCurrentDraft: () => string;
};

export type RunStreamResult = "aborted" | "completed" | "error";

type AttachActiveStreamOptions = {
  conversation: ConversationDetail;
  errorMessage: string;
  request: (handlers: {
    onEvent: (event: ChatStreamEvent) => void;
    signal: AbortSignal;
  }) => Promise<void>;
};

export function useConversationStreams({
  activeConversation,
  activeConversationId,
  setActiveConversation,
  setActiveConversationId,
  setConversations,
  setError,
  setSelectedModel,
}: UseConversationStreamsOptions) {
  const [streamSessions, setStreamSessions] = useState<Record<string, StreamSession>>({});
  const activeConversationIdRef = useRef<number | null>(activeConversationId);
  const pendingStageTimeoutsRef = useRef<Record<string, number>>({});
  const sessionControllersRef = useRef<Record<string, AbortController>>({});
  const streamSessionsRef = useRef<Record<string, StreamSession>>({});

  const setStreamSessionsState = useCallback(
    (updater: (current: Record<string, StreamSession>) => Record<string, StreamSession>) => {
      setStreamSessions((current) => {
        const next = updater(current);
        streamSessionsRef.current = next;
        return next;
      });
    },
    [],
  );

  const clearSessionStageTimeout = useCallback((conversationId: number) => {
    const key = streamSessionKey(conversationId);
    const timeoutId = pendingStageTimeoutsRef.current[key];
    if (timeoutId) {
      window.clearTimeout(timeoutId);
      delete pendingStageTimeoutsRef.current[key];
    }
  }, []);

  const upsertConversationSummary = useCallback(
    (conversation: ConversationDetail) => {
      if (conversation.id <= 0) {
        return;
      }

      setConversations((current) =>
        sortConversations([
          toConversationSummary(conversation),
          ...current.filter((item) => item.id !== conversation.id),
        ]),
      );
    },
    [setConversations],
  );

  const removeStreamSession = useCallback(
    (conversationId: number) => {
      const key = streamSessionKey(conversationId);
      clearSessionStageTimeout(conversationId);
      delete sessionControllersRef.current[key];
      setStreamSessionsState((current) => {
        if (!current[key]) {
          return current;
        }

        const { [key]: _removed, ...rest } = current;
        return rest;
      });
    },
    [clearSessionStageTimeout, setStreamSessionsState],
  );

  const updateStreamSession = useCallback(
    (conversationId: number, updater: (session: StreamSession) => StreamSession) => {
      const key = streamSessionKey(conversationId);
      setStreamSessionsState((current) => {
        const session = current[key];
        if (!session) {
          return current;
        }

        const nextSession = updater(session);
        if (nextSession === session) {
          return current;
        }

        return {
          ...current,
          [key]: nextSession,
        };
      });
    },
    [setStreamSessionsState],
  );

  const updateSessionConversation = useCallback(
    (conversationId: number, updater: ConversationUpdater) => {
      updateStreamSession(conversationId, (session) => ({
        ...session,
        conversation: updater(session.conversation),
      }));
      setActiveConversation((current) =>
        current && current.id === conversationId ? updater(current) : current,
      );
    },
    [setActiveConversation, updateStreamSession],
  );

  const moveStreamSession = useCallback(
    (fromConversationId: number, toConversationId: number) => {
      if (fromConversationId === toConversationId) {
        return;
      }

      const fromKey = streamSessionKey(fromConversationId);
      const toKey = streamSessionKey(toConversationId);
      setStreamSessionsState((current) => {
        const session = current[fromKey];
        if (!session) {
          return current;
        }

        const { [fromKey]: _removed, ...rest } = current;
        return {
          ...rest,
          [toKey]: {
            ...session,
            conversation: {
              ...session.conversation,
              id: toConversationId,
            },
          },
        };
      });

      const controller = sessionControllersRef.current[fromKey];
      if (controller) {
        delete sessionControllersRef.current[fromKey];
        sessionControllersRef.current[toKey] = controller;
      }

      const timeoutId = pendingStageTimeoutsRef.current[fromKey];
      if (timeoutId) {
        delete pendingStageTimeoutsRef.current[fromKey];
        pendingStageTimeoutsRef.current[toKey] = timeoutId;
      }

      setActiveConversation((current) =>
        current && current.id === fromConversationId
          ? { ...current, id: toConversationId }
          : current,
      );
    },
    [setActiveConversation, setStreamSessionsState],
  );

  const commitSessionStage = useCallback(
    (conversationId: number, nextStage: StreamingStage | null) => {
      clearSessionStageTimeout(conversationId);
      updateStreamSession(conversationId, (session) => ({
        ...session,
        stage: nextStage,
        stageStartedAt: nextStage ? Date.now() : 0,
      }));
    },
    [clearSessionStageTimeout, updateStreamSession],
  );

  const transitionSessionStage = useCallback(
    (conversationId: number, nextStage: StreamingStage | null) => {
      const session = streamSessionsRef.current[streamSessionKey(conversationId)];
      if (!session || session.stage === nextStage) {
        return;
      }

      clearSessionStageTimeout(conversationId);
      if (session.stage && nextStage) {
        const minDisplayMs = MIN_STAGE_DISPLAY_MS[session.stage] ?? 0;
        const elapsed = Date.now() - session.stageStartedAt;
        if (minDisplayMs > elapsed) {
          pendingStageTimeoutsRef.current[streamSessionKey(conversationId)] = window.setTimeout(
            () => {
              delete pendingStageTimeoutsRef.current[streamSessionKey(conversationId)];
              updateStreamSession(conversationId, (current) => ({
                ...current,
                stage: nextStage,
                stageStartedAt: Date.now(),
              }));
            },
            minDisplayMs - elapsed,
          );
          return;
        }
      }

      updateStreamSession(conversationId, (current) => ({
        ...current,
        stage: nextStage,
        stageStartedAt: nextStage ? Date.now() : 0,
      }));
    },
    [clearSessionStageTimeout, updateStreamSession],
  );

  const settleStreamSession = useCallback(
    (conversationId: number, status: StreamSessionStatus) => {
      clearSessionStageTimeout(conversationId);
      delete sessionControllersRef.current[streamSessionKey(conversationId)];

      const isActiveConversation = activeConversationIdRef.current === conversationId;
      if (status === "completed" && isActiveConversation) {
        removeStreamSession(conversationId);
        return;
      }

      updateStreamSession(conversationId, (session) => ({
        ...session,
        stage: null,
        stageStartedAt: 0,
        status,
        unread: isActiveConversation ? false : true,
      }));
    },
    [clearSessionStageTimeout, removeStreamSession, updateStreamSession],
  );

  const handleStreamEvent = useCallback(
    (conversationId: number, event: ChatStreamEvent) => {
      const currentSession = streamSessionsRef.current[streamSessionKey(conversationId)];
      const currentLastSeq = currentSession?.conversation.active_run?.last_seq ?? 0;
      if (
        typeof event.seq === "number"
        && Number.isFinite(event.seq)
        && event.seq <= currentLastSeq
      ) {
        return;
      }

      if (
        (typeof event.run_id === "string" && event.run_id.trim())
        || (typeof event.seq === "number" && Number.isFinite(event.seq))
      ) {
        updateSessionConversation(conversationId, (current) => ({
          ...current,
          active_run: {
            action: current.active_run?.action ?? "run",
            started_at: current.active_run?.started_at ?? null,
            run_id:
              typeof event.run_id === "string" && event.run_id.trim()
                ? event.run_id.trim()
                : current.active_run?.run_id ?? null,
            last_seq: Math.max(current.active_run?.last_seq ?? 0, event.seq ?? 0) || null,
          },
        }));
      }

      if (event.type === "token") {
        const cleanContent = sanitizeTokenContent(event.content);
        updateStreamSession(conversationId, (session) => {
          if (!session.reasoningStreaming) {
            return session;
          }
          if (!cleanContent && !shouldCloseReasoningStream(session, event.content, cleanContent)) {
            return session;
          }
          // 中文注释：只要正文 token 开始，前端就把“思考中”收束成已完成态；推理摘要仍保留在草稿消息上。
          return {
            ...session,
            reasoningStreaming: false,
          };
        });
        if (!cleanContent) {
          return;
        }
        updateSessionConversation(conversationId, (current) =>
          appendAssistantDraftContent(current, cleanContent),
        );
        commitSessionStage(conversationId, null);
        return;
      }

      if (event.type === "reasoning") {
        updateSessionConversation(conversationId, (current) =>
          appendAssistantDraftReasoning(current, event.content),
        );
        updateStreamSession(conversationId, (session) => ({
          ...session,
          reasoning: session.reasoning + event.content,
          reasoningStreaming: true,
        }));
        commitSessionStage(conversationId, null);
        return;
      }

      if (event.type === "sources") {
        updateSessionConversation(conversationId, (current) =>
          setAssistantDraftSources(current, event.sources),
        );
        return;
      }

      if (event.type === "search_trace") {
        updateSessionConversation(conversationId, (current) =>
          setAssistantDraftSearchTrace(current, {
            queries: event.queries,
            sources: event.sources,
          }),
        );
        return;
      }

      if (event.type === "context") {
        updateStreamSession(conversationId, (session) => ({
          ...session,
          pendingContext: event.context,
        }));
        return;
      }

      if (event.type === "status") {
        const nextStage = stageFromStatusItems(event.items);
        if (nextStage || event.items.length === 0) {
          transitionSessionStage(conversationId, nextStage);
        }
        return;
      }

      if (event.type === "done") {
        return;
      }

      if (event.type === "error") {
        updateSessionConversation(conversationId, (current) =>
          replaceAssistantDraftWithError(current, event.message),
        );
        const session = streamSessionsRef.current[streamSessionKey(conversationId)];
        if (session) {
          upsertConversationSummary(session.conversation);
        }
        setError(event.message);
        settleStreamSession(conversationId, "error");
      }
    },
    [
      commitSessionStage,
      settleStreamSession,
      setError,
      transitionSessionStage,
      updateSessionConversation,
      updateStreamSession,
      upsertConversationSummary,
    ],
  );

  const runStream = useCallback(
    async ({
      conversation,
      errorMessage,
      initialStage,
      restoreInput,
      tempUserMessageId,
      request,
    }: RunStreamOptions): Promise<RunStreamResult> => {
      let streamConversationId = conversation.id;
      const initialSession: StreamSession = {
        conversation,
        pendingContext: null,
        reasoning: "",
        reasoningStreaming: false,
        restoreInput,
        stage: initialStage,
        stageStartedAt: initialStage ? Date.now() : 0,
        status: "running",
        unread: false,
      };

      setStreamSessionsState((current) => ({
        ...current,
        [streamSessionKey(streamConversationId)]: initialSession,
      }));
      setError(null);
      upsertConversationSummary(conversation);

      const controller = new AbortController();
      sessionControllersRef.current[streamSessionKey(streamConversationId)] = controller;

      try {
        await request({
          onEvent: (event) => {
            if (event.type === "meta") {
              const previousConversationId = streamConversationId;
              const nextConversationId = event.conversation_id;
              const previousSession =
                streamSessionsRef.current[streamSessionKey(previousConversationId)];
              streamConversationId = nextConversationId;

              moveStreamSession(previousConversationId, nextConversationId);

              if (previousSession) {
                const nextConversation = replaceConversationMessageId(
                  {
                    ...previousSession.conversation,
                    id: nextConversationId,
                    model: event.model,
                    temporary_chat: previousSession.conversation.temporary_chat,
                  },
                  tempUserMessageId,
                  event.message_id,
                );
                updateSessionConversation(nextConversationId, () =>
                  setAssistantDraftModel(nextConversation, event.model),
                );
                upsertConversationSummary(nextConversation);
              }

              if (activeConversationIdRef.current === previousConversationId) {
                setActiveConversationId(nextConversationId);
                setSelectedModel(event.model);
              }
              return;
            }

            if (event.type === "done") {
              const session = streamSessionsRef.current[streamSessionKey(streamConversationId)];
              if (session) {
                const completedConversation = finalizeAssistantDraft(session, event);
                updateSessionConversation(streamConversationId, () => completedConversation);
                upsertConversationSummary(completedConversation);
              }

              settleStreamSession(streamConversationId, "completed");
              return;
            }

            handleStreamEvent(streamConversationId, event);
          },
          signal: controller.signal,
        });

        if (streamSessionsRef.current[streamSessionKey(streamConversationId)]?.status === "running") {
          settleStreamSession(streamConversationId, "completed");
        }

        const finalSession = streamSessionsRef.current[streamSessionKey(streamConversationId)];
        return finalSession?.status === "error" ? "error" : "completed";
      } catch (streamError) {
        if (isAbortError(streamError)) {
          return "aborted";
        }

        const message = toStreamErrorMessage(streamError, errorMessage);
        setError(message);
        updateSessionConversation(streamConversationId, (current) =>
          replaceAssistantDraftWithError(current, message),
        );
        const session = streamSessionsRef.current[streamSessionKey(streamConversationId)];
        if (session) {
          upsertConversationSummary(session.conversation);
        }
        settleStreamSession(streamConversationId, "error");
        return "error";
      } finally {
        delete sessionControllersRef.current[streamSessionKey(streamConversationId)];
        clearSessionStageTimeout(streamConversationId);
      }
    },
    [
      clearSessionStageTimeout,
      handleStreamEvent,
      moveStreamSession,
      setActiveConversationId,
      setError,
      setSelectedModel,
      setStreamSessionsState,
      settleStreamSession,
      updateSessionConversation,
      upsertConversationSummary,
    ],
  );

  const attachActiveStream = useCallback(
    async ({ conversation, errorMessage, request }: AttachActiveStreamOptions): Promise<RunStreamResult> => {
      const existingSession = streamSessionsRef.current[streamSessionKey(conversation.id)];
      if (existingSession?.status === "running") {
        setActiveConversation(existingSession.conversation);
        setSelectedModel(existingSession.conversation.model);
        return "completed";
      }

      const attachedConversation = ensureAssistantDraftMessage(conversation, conversation.model);
      setActiveConversation((current) =>
        current && current.id === attachedConversation.id ? attachedConversation : current,
      );
      setSelectedModel(attachedConversation.model);

      return runStream({
        conversation: attachedConversation,
        errorMessage,
        initialStage: "waiting_for_model",
        restoreInput: {
          content: "",
          loadFiles: async () => [],
          restoreToComposerOnStop: false,
        },
        tempUserMessageId: "active-run-resume",
        request,
      });
    },
    [runStream, setActiveConversation, setSelectedModel],
  );

  const stopStream = useCallback(
    async ({ conversationId, restoreAttachments, restoreDraft, getCurrentDraft }: StopStreamOptions) => {
      const key = streamSessionKey(conversationId);
      const session = streamSessionsRef.current[key];
      const controller = sessionControllersRef.current[key];
      if (!session || session.status !== "running" || !controller) {
        return;
      }

      const shouldRestoreComposer = session.restoreInput.restoreToComposerOnStop !== false;
      if (shouldRestoreComposer) {
        // Only restore the original draft if the user hasn't started typing new content
        if (!getCurrentDraft()) {
          restoreDraft(session.restoreInput.content);
        }
      }
      updateSessionConversation(conversationId, markAssistantDraftStopped);
      const cancelRequest = cancelActiveChat(conversationId);
      controller.abort();
      try {
        // 中文注释：先等后端确认取消，再把本地 running 放掉，避免用户立刻 Enter 触发残留 active run。
        await cancelRequest;
      } catch (cancelError) {
        setError(cancelError instanceof Error ? cancelError.message : "Failed to cancel active response.");
      }
      settleStreamSession(conversationId, "stopped");

      const stoppedSession = streamSessionsRef.current[key];
      if (stoppedSession) {
        upsertConversationSummary(stoppedSession.conversation);
      }

      if (shouldRestoreComposer) {
        try {
          restoreAttachments(await session.restoreInput.loadFiles());
        } catch (restoreError) {
          setError(
            restoreError instanceof Error ? restoreError.message : "Failed to restore attachments.",
          );
        }
      }
    },
    [
      setError,
      settleStreamSession,
      updateSessionConversation,
      upsertConversationSummary,
    ],
  );

  const mergeConversationSummariesWithSessions = useCallback(
    (items: ConversationSummary[]) => mergeConversationSummaries(items, streamSessionsRef.current),
    [],
  );

  const getSessionConversation = useCallback((conversationId: number) => {
    return streamSessionsRef.current[streamSessionKey(conversationId)]?.conversation ?? null;
  }, []);

  const openSessionConversation = useCallback(
    (conversationId: number) => {
      const session = streamSessionsRef.current[streamSessionKey(conversationId)];
      if (!session) {
        return;
      }

      setActiveConversation(session.conversation);
      setSelectedModel(session.conversation.model);

      if (session.status === "completed") {
        removeStreamSession(conversationId);
        return;
      }

      if (session.unread) {
        updateStreamSession(conversationId, (current) => ({
          ...current,
          unread: false,
        }));
      }
    },
    [removeStreamSession, setActiveConversation, setSelectedModel, updateStreamSession],
  );

  const renameSession = useCallback(
    (conversationId: number, title: string) => {
      updateStreamSession(conversationId, (session) => ({
        ...session,
        conversation: {
          ...session.conversation,
          title,
        },
      }));
    },
    [updateStreamSession],
  );

  const abortAndRemoveSession = useCallback(
    (conversationId: number) => {
      sessionControllersRef.current[streamSessionKey(conversationId)]?.abort();
      removeStreamSession(conversationId);
    },
    [removeStreamSession],
  );

  useEffect(() => {
    streamSessionsRef.current = streamSessions;
  }, [streamSessions]);

  useEffect(() => {
    activeConversationIdRef.current = activeConversationId;
  }, [activeConversationId]);

  useEffect(() => {
    return () => {
      Object.values(streamSessionsRef.current).forEach((session) => {
        if (session.status === "running" && session.conversation.id > 0) {
          // 中文注释：组件卸载时也要通知后端取消，否则仅 abort fetch 会让后台模型流继续占并发槽。
          void cancelActiveChat(session.conversation.id).catch((error: unknown) => {
            console.error("Failed to cancel active chat on unmount", error);
          });
        }
      });
      Object.values(sessionControllersRef.current).forEach((controller) => controller.abort());
      Object.values(pendingStageTimeoutsRef.current).forEach((timeoutId) => {
        window.clearTimeout(timeoutId);
      });
    };
  }, []);

  const activeSession = activeConversation
    ? streamSessions[streamSessionKey(activeConversation.id)] ?? null
    : null;
  const isStreaming = activeSession?.status === "running";
  const visibleStreaming =
    isStreaming &&
    activeConversation !== null &&
    activeConversation.messages.some((item) => item.id === ASSISTANT_DRAFT_ID);

  const conversationActivity = useMemo<Record<number, ConversationActivity>>(
    () =>
      Object.values(streamSessions).reduce<Record<number, ConversationActivity>>((acc, session) => {
        if (session.conversation.id > 0) {
          acc[session.conversation.id] = {
            running: session.status === "running",
            unread: session.unread,
          };
        }
        return acc;
      }, {}),
    [streamSessions],
  );
  const runningSessions = useMemo(
    () => Object.values(streamSessions).filter((session) => session.status === "running"),
    [streamSessions],
  );

  return {
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
  };
}
