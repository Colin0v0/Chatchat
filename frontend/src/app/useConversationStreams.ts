import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";

import type { ChatStreamEvent, ConversationDetail, ConversationSummary } from "../types";
import { ASSISTANT_DRAFT_ID } from "./constants";
import {
  appendAssistantDraftContent,
  ConversationActivity,
  ConversationUpdater,
  isAbortError,
  markAssistantDraftStopped,
  mergeConversationSummaries,
  replaceAssistantDraftWithError,
  replaceConversationMessageId,
  RunStreamOptions,
  setAssistantDraftId,
  setAssistantDraftSources,
  sortConversations,
  stageFromStatusItems,
  StreamSession,
  StreamSessionStatus,
  streamSessionKey,
  StreamingStage,
  toConversationSummary,
  toStreamErrorMessage,
} from "./chatSessionUtils";

const MIN_STAGE_DISPLAY_MS: Partial<Record<StreamingStage, number>> = {
  analyzing_attachments: 720,
};

type UseConversationStreamsOptions = {
  activeConversation: ConversationDetail | null;
  activeConversationId: number | null;
  setActiveConversation: Dispatch<SetStateAction<ConversationDetail | null>>;
  setActiveConversationId: Dispatch<SetStateAction<number | null>>;
  setConversations: Dispatch<SetStateAction<ConversationSummary[]>>;
  setError: Dispatch<SetStateAction<string | null>>;
  setSelectedModel: Dispatch<SetStateAction<string>>;
  setThinkingExpanded: Dispatch<SetStateAction<boolean>>;
};

type StopStreamOptions = {
  conversationId: number;
  restoreAttachments: (files: File[]) => void;
  restoreDraft: (content: string) => void;
};

export type RunStreamResult = "aborted" | "completed" | "error";

export function useConversationStreams({
  activeConversation,
  activeConversationId,
  setActiveConversation,
  setActiveConversationId,
  setConversations,
  setError,
  setSelectedModel,
  setThinkingExpanded,
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
      if (event.type === "token") {
        updateSessionConversation(conversationId, (current) =>
          appendAssistantDraftContent(current, event.content),
        );
        commitSessionStage(conversationId, null);
        return;
      }

      if (event.type === "reasoning") {
        updateStreamSession(conversationId, (session) => ({
          ...session,
          reasoning: session.reasoning + event.content,
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

      if (event.type === "status") {
        const nextStage = stageFromStatusItems(event.items);
        if (nextStage) {
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
        reasoning: "",
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
      setThinkingExpanded(false);
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
                  },
                  tempUserMessageId,
                  event.message_id,
                );
                updateSessionConversation(nextConversationId, () => nextConversation);
                upsertConversationSummary(nextConversation);
              }

              if (activeConversationIdRef.current === previousConversationId) {
                setActiveConversationId(nextConversationId);
                setSelectedModel(event.model);
              }
              return;
            }

            if (event.type === "done") {
              if (event.assistant_message_id != null) {
                const session = streamSessionsRef.current[streamSessionKey(streamConversationId)];
                if (session) {
                  const nextConversation = setAssistantDraftId(
                    session.conversation,
                    event.assistant_message_id,
                  );
                  updateSessionConversation(streamConversationId, () => nextConversation);
                  upsertConversationSummary(nextConversation);
                }
              } else {
                const session = streamSessionsRef.current[streamSessionKey(streamConversationId)];
                if (session) {
                  upsertConversationSummary(session.conversation);
                }
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
      setThinkingExpanded,
      settleStreamSession,
      updateSessionConversation,
      upsertConversationSummary,
    ],
  );

  const stopStream = useCallback(
    async ({ conversationId, restoreAttachments, restoreDraft }: StopStreamOptions) => {
      const key = streamSessionKey(conversationId);
      const session = streamSessionsRef.current[key];
      const controller = sessionControllersRef.current[key];
      if (!session || session.status !== "running" || !controller) {
        return;
      }

      restoreDraft(session.restoreInput.content);
      setThinkingExpanded(false);
      updateSessionConversation(conversationId, markAssistantDraftStopped);
      settleStreamSession(conversationId, "stopped");
      controller.abort();

      const stoppedSession = streamSessionsRef.current[key];
      if (stoppedSession) {
        upsertConversationSummary(stoppedSession.conversation);
      }

      try {
        restoreAttachments(await session.restoreInput.loadFiles());
      } catch (restoreError) {
        setError(
          restoreError instanceof Error ? restoreError.message : "Failed to restore attachments.",
        );
      }
    },
    [
      setError,
      setThinkingExpanded,
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
