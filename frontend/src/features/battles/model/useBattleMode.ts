import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useLatestRequestGuard } from "../../../shared/hooks/useLatestRequestGuard";
import type { BattleSessionSummary, MessageAttachment, ModelOption, ToolMode } from "../../../types";
import { deriveConversationTitle } from "../../chats/lib/constants";
import {
  reasoningRequestValueForModel,
  resolveModelDefaultReasoningProfile,
} from "../../models/lib/reasoningProfiles";
import type { PetSignalType } from "../../pet/model/petSignals";
import {
  createBattleSession,
  deleteBattleSession,
  fetchBattleSession,
  fetchBattleSessions,
  renameBattleSession,
  streamBattleResponse,
  updateBattleSession,
} from "../api/battle";
import type { BattleRound, BattleSessionDetail, BattleVote } from "./types";

interface UseBattleModeOptions {
  availableModels: ModelOption[];
  draftFiles: File[];
  knowledgeFolders: string[];
  onDraftAccepted?: () => void;
  onModelLoveScoreChange?: (modelId: string, delta: number) => void;
  onModelUsageCountChange?: (modelId: string, delta: number) => void;
  onPetEvent?: (type: PetSignalType) => void;
  query: string;
  setError: (message: string | null) => void;
  toolMode: ToolMode;
  userId: number | null;
}

function battleSessionSummary(session: BattleSessionDetail): BattleSessionSummary {
  const latestRound = session.rounds.at(-1);
  return {
    id: session.id,
    title: session.title,
    updated_at: session.updated_at,
    last_message_preview: latestRound?.prompt ?? "",
  };
}

function createBattleRound({
  attachments,
  firstModel,
  prompt,
  secondModel,
}: {
  attachments: MessageAttachment[];
  firstModel: ModelOption;
  prompt: string;
  secondModel: ModelOption;
}): BattleRound {
  const startedAt = Date.now();
  return {
    id: `battle-round-${startedAt}`,
    prompt,
    createdAt: new Date(startedAt).toISOString(),
    revealed: false,
    vote: null,
    attachments,
    sides: {
      a: {
        id: "a",
        model: firstModel,
        content: "",
        reasoning: "",
        status: "streaming",
        error: null,
        startedAt,
        finishedAt: null,
      },
      b: {
        id: "b",
        model: secondModel,
        content: "",
        reasoning: "",
        status: "streaming",
        error: null,
        startedAt,
        finishedAt: null,
      },
    },
  };
}

const IMAGE_ATTACHMENT_EXTENSIONS = new Set([".gif", ".jpeg", ".jpg", ".png", ".webp"]);

function fileExtension(name: string) {
  const dotIndex = name.lastIndexOf(".");
  return dotIndex >= 0 ? name.slice(dotIndex).toLowerCase() : "";
}

function fileLooksLikeImage(file: File) {
  return file.type.startsWith("image/") || IMAGE_ATTACHMENT_EXTENSIONS.has(fileExtension(file.name));
}

function modelSupportsBattleRequest(modelOption: ModelOption, files: File[]) {
  if (modelOption.capabilities?.input.text !== true || modelOption.capabilities.stream.text !== true) {
    return false;
  }

  for (const file of files) {
    const extension = fileExtension(file.name);
    if (fileLooksLikeImage(file) && modelOption.capabilities.input.image !== true) {
      return false;
    }
    if (extension === ".pdf" && modelOption.capabilities.input.pdf !== true) {
      return false;
    }
    if (!fileLooksLikeImage(file) && extension !== ".pdf" && modelOption.capabilities.input.other_file !== true) {
      return false;
    }
  }

  return true;
}

function attachmentPromptLabel(files: File[]) {
  const names = files.map((file) => file.name).filter(Boolean);
  return names.length > 0 ? `附件：${names.join("、")}` : "";
}

function sortBattleSummaries(items: BattleSessionSummary[]) {
  return [...items].sort((left, right) => {
    const leftTime = left.updated_at ? Date.parse(left.updated_at) : 0;
    const rightTime = right.updated_at ? Date.parse(right.updated_at) : 0;
    if (rightTime !== leftTime) {
      return rightTime - leftTime;
    }
    return right.id - left.id;
  });
}

function mergeBattleSideState(
  serverSide: BattleRound["sides"]["a"],
  cachedSide: BattleRound["sides"]["a"],
): BattleRound["sides"]["a"] {
  return {
    ...serverSide,
    content:
      cachedSide.content.length > serverSide.content.length
        ? cachedSide.content
        : serverSide.content,
    reasoning:
      cachedSide.reasoning.length > serverSide.reasoning.length
        ? cachedSide.reasoning
        : serverSide.reasoning,
    status:
      serverSide.status === "streaming" && cachedSide.status !== "streaming"
        ? cachedSide.status
        : serverSide.status,
    error: cachedSide.error ?? serverSide.error,
    startedAt: cachedSide.startedAt || serverSide.startedAt,
    finishedAt: serverSide.finishedAt ?? cachedSide.finishedAt,
  };
}

function mergeBattleRound(serverRound: BattleRound, cachedRound: BattleRound): BattleRound {
  return {
    ...serverRound,
    revealed: serverRound.revealed || cachedRound.revealed,
    vote: cachedRound.vote ?? serverRound.vote,
    attachments:
      cachedRound.attachments.length > serverRound.attachments.length
        ? cachedRound.attachments
        : serverRound.attachments,
    sides: {
      a: mergeBattleSideState(serverRound.sides.a, cachedRound.sides.a),
      b: mergeBattleSideState(serverRound.sides.b, cachedRound.sides.b),
    },
  };
}

function mergeBattleSessionWithCache(
  serverSession: BattleSessionDetail,
  cachedSession: BattleSessionDetail | null,
): BattleSessionDetail {
  if (!cachedSession || cachedSession.id !== serverSession.id) {
    return serverSession;
  }

  const cachedRoundsById = new Map(cachedSession.rounds.map((round) => [round.id, round]));
  const mergedRounds = serverSession.rounds.map((round) => {
    const cachedRound = cachedRoundsById.get(round.id);
    return cachedRound ? mergeBattleRound(round, cachedRound) : round;
  });
  const knownRoundIds = new Set(mergedRounds.map((round) => round.id));
  const cachedOnlyRounds = cachedSession.rounds.filter((round) => !knownRoundIds.has(round.id));

  return {
    ...serverSession,
    updated_at:
      cachedSession.updated_at && serverSession.updated_at
        ? (
            Date.parse(cachedSession.updated_at) > Date.parse(serverSession.updated_at)
              ? cachedSession.updated_at
              : serverSession.updated_at
          )
        : cachedSession.updated_at ?? serverSession.updated_at,
    rounds: [...mergedRounds, ...cachedOnlyRounds],
  };
}

export function useBattleMode({
  availableModels,
  draftFiles,
  knowledgeFolders,
  onDraftAccepted,
  onModelLoveScoreChange,
  onModelUsageCountChange,
  onPetEvent,
  query,
  setError,
  toolMode,
  userId,
}: UseBattleModeOptions) {
  const [sessions, setSessions] = useState<BattleSessionSummary[]>([]);
  const [sessionsLoaded, setSessionsLoaded] = useState(false);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [activeSession, setActiveSession] = useState<BattleSessionDetail | null>(null);
  const [draft, setDraft] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllersRef = useRef<AbortController[]>([]);
  const loadAbortRef = useRef<AbortController | null>(null);
  const sessionCacheRef = useRef<Map<number, BattleSessionDetail>>(new Map());
  const sessionRevisionRef = useRef<Map<number, number>>(new Map());
  const persistQueueRef = useRef<Promise<void>>(Promise.resolve());
  const activeIdRef = useRef<number | null>(null);
  const activeSessionRef = useRef<BattleSessionDetail | null>(null);
  const streamingSessionIdRef = useRef<number | null>(null);
  const refreshGuard = useLatestRequestGuard();
  const loadGuard = useLatestRequestGuard();

  const filteredSessions = useMemo(() => {
    if (!query.trim()) {
      return sessions;
    }

    const keyword = query.toLowerCase();
    return sessions.filter((item) => item.title.toLowerCase().includes(keyword));
  }, [query, sessions]);

  useEffect(() => {
    activeIdRef.current = activeId;
  }, [activeId]);

  useEffect(() => {
    activeSessionRef.current = activeSession;
  }, [activeSession]);

  const abortStreams = useCallback(() => {
    abortControllersRef.current.forEach((controller) => controller.abort());
    abortControllersRef.current = [];
  }, []);

  const upsertSessionSummary = useCallback((summary: BattleSessionSummary) => {
    setSessions((current) => {
      const next = current.filter((item) => item.id !== summary.id);
      next.push(summary);
      return sortBattleSummaries(next);
    });
  }, []);

  const removeSessionSummary = useCallback((sessionId: number) => {
    setSessions((current) => current.filter((session) => session.id !== sessionId));
  }, []);

  const commitSession = useCallback((session: BattleSessionDetail) => {
    const nextRevision = (sessionRevisionRef.current.get(session.id) ?? 0) + 1;
    sessionRevisionRef.current.set(session.id, nextRevision);
    sessionCacheRef.current.set(session.id, session);
    upsertSessionSummary(battleSessionSummary(session));
    setActiveSession((current) =>
      (current && current.id === session.id) || activeIdRef.current === session.id ? session : current,
    );
    return nextRevision;
  }, [upsertSessionSummary]);

  const getKnownSession = useCallback((sessionId: number) => {
    const cachedSession = sessionCacheRef.current.get(sessionId);
    if (cachedSession) {
      return cachedSession;
    }
    if (activeSessionRef.current?.id === sessionId) {
      return activeSessionRef.current;
    }
    return null;
  }, []);

  const updateKnownSession = useCallback(
    (
      sessionId: number,
      update: (session: BattleSessionDetail) => BattleSessionDetail,
    ) => {
      const currentSession = getKnownSession(sessionId);
      if (!currentSession) {
        return null;
      }

      const nextSession = update(currentSession);
      const revision = commitSession(nextSession);
      return {
        revision,
        session: nextSession,
      };
    },
    [commitSession, getKnownSession],
  );

  const enqueuePersist = useCallback(<T,>(task: () => Promise<T>) => {
    const nextTask = persistQueueRef.current.then(() => task(), () => task());
    persistQueueRef.current = nextTask.then(() => undefined, () => undefined);
    return nextTask;
  }, []);

  const persistSessionSnapshot = useCallback(
    (session: BattleSessionDetail, revision: number) => {
      return enqueuePersist(async () => {
        try {
          const savedSession = await updateBattleSession(session.id, {
            title: session.title,
            rounds: session.rounds,
          });
          if ((sessionRevisionRef.current.get(session.id) ?? 0) !== revision) {
            return false;
          }
          commitSession(savedSession);
          return true;
        } catch (persistError) {
          setError(persistError instanceof Error ? persistError.message : "Battle 保存失败。");
          return false;
        }
      });
    },
    [commitSession, enqueuePersist, setError],
  );

  const updateRound = useCallback(
    (
      sessionId: number,
      roundId: string,
      update: (round: BattleRound) => BattleRound,
      options?: { touchUpdatedAt?: boolean },
    ) =>
      updateKnownSession(sessionId, (session) => ({
        ...session,
        updated_at:
          options?.touchUpdatedAt === false
            ? session.updated_at
            : new Date().toISOString(),
        rounds: session.rounds.map((round) => (round.id === roundId ? update(round) : round)),
      })),
    [updateKnownSession],
  );

  const chooseModels = useCallback((files: File[]): [ModelOption, ModelOption] | null => {
    const candidates = availableModels.filter((modelOption) => modelSupportsBattleRequest(modelOption, files));
    if (candidates.length < 2) {
      setError(files.length > 0 ? "Battle 至少需要两个支持当前附件类型的模型。" : "Battle 至少需要两个可用文本模型。");
      return null;
    }

    const firstIndex = Math.floor(Math.random() * candidates.length);
    let secondIndex = Math.floor(Math.random() * (candidates.length - 1));
    if (secondIndex >= firstIndex) {
      secondIndex += 1;
    }
    return [candidates[firstIndex], candidates[secondIndex]];
  }, [availableModels, setError]);

  const refreshSessions = useCallback(async () => {
    if (userId === null) {
      setSessions([]);
      setSessionsLoaded(true);
      return;
    }

    const requestId = refreshGuard.begin();
    try {
      const items = await fetchBattleSessions();
      if (!refreshGuard.isCurrent(requestId)) {
        return;
      }
      setSessions(sortBattleSummaries(items));
    } catch (refreshError) {
      if (refreshGuard.isCurrent(requestId)) {
        setError(refreshError instanceof Error ? refreshError.message : "Battle 列表加载失败。");
      }
    } finally {
      if (refreshGuard.isCurrent(requestId)) {
        setSessionsLoaded(true);
      }
    }
  }, [refreshGuard, setError, userId]);

  const loadSession = useCallback(
    async (sessionId: number) => {
      const requestId = loadGuard.begin();
      loadAbortRef.current?.abort();

      const cachedSession = getKnownSession(sessionId);
      if (cachedSession) {
        setActiveSession(cachedSession);
      }

      const controller = new AbortController();
      loadAbortRef.current = controller;

      try {
        const session = mergeBattleSessionWithCache(
          await fetchBattleSession(sessionId, controller.signal),
          getKnownSession(sessionId),
        );
        if (controller.signal.aborted || !loadGuard.isCurrent(requestId)) {
          return;
        }
        commitSession(session);
      } catch (loadError) {
        if (controller.signal.aborted || !loadGuard.isCurrent(requestId)) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Battle 会话加载失败。");
      } finally {
        if (loadAbortRef.current === controller) {
          loadAbortRef.current = null;
        }
      }
    },
    [commitSession, getKnownSession, loadGuard, setError],
  );

  useEffect(() => {
    abortStreams();
    loadAbortRef.current?.abort();
    activeIdRef.current = null;
    streamingSessionIdRef.current = null;
    setIsStreaming(false);
    setActiveId(null);
    setActiveSession(null);
    setDraft("");
    setSessionsLoaded(false);
    sessionCacheRef.current.clear();
    sessionRevisionRef.current.clear();
    void refreshSessions();
  }, [abortStreams, refreshSessions, userId]);

  useEffect(() => {
    if (activeId === null) {
      return;
    }

    void loadSession(activeId);
  }, [activeId, loadSession]);

  useEffect(() => {
    return () => {
      abortStreams();
      loadAbortRef.current?.abort();
    };
  }, [abortStreams]);

  const markStoppedSession = useCallback((sessionId: number) => {
    const stoppedAt = Date.now();
    return updateKnownSession(sessionId, (session) => {
      const latestRoundIndex = session.rounds.length - 1;
      return {
        ...session,
        updated_at: new Date(stoppedAt).toISOString(),
        rounds: session.rounds.map((round, index) => {
          if (index !== latestRoundIndex) {
            return round;
          }

          const markStopped = (side: BattleRound["sides"]["a"]) =>
            side.status === "streaming"
              ? {
                  ...side,
                  status: "error" as const,
                  error: "已停止生成。",
                  finishedAt: stoppedAt,
                }
              : side;

          return {
            ...round,
            sides: {
              a: markStopped(round.sides.a),
              b: markStopped(round.sides.b),
            },
          };
        }),
      };
    });
  }, [updateKnownSession]);

  const startNewSession = useCallback(() => {
    activeIdRef.current = null;
    setActiveId(null);
    setActiveSession(null);
    setDraft("");
  }, []);

  const selectSession = useCallback((sessionId: number) => {
    activeIdRef.current = sessionId;
    setActiveId(sessionId);
    setActiveSession(getKnownSession(sessionId));
  }, [getKnownSession]);

  const clearActiveSession = useCallback(() => {
    activeIdRef.current = null;
    setActiveId(null);
    setActiveSession(null);
  }, []);

  const vote = useCallback(
    (roundId: string, nextVote: BattleVote) => {
      if (activeId === null) {
        return;
      }

      const currentRound = getKnownSession(activeId)?.rounds.find((round) => round.id === roundId);
      const updated = updateRound(activeId, roundId, (round) => ({
        ...round,
        revealed: true,
        vote: nextVote,
      }));
      if (!updated) {
        return;
      }

      void persistSessionSnapshot(updated.session, updated.revision);
      if (nextVote === "a" || nextVote === "b") {
        const winningModelId = currentRound?.sides[nextVote].model.id;
        if (winningModelId) {
          onModelLoveScoreChange?.(winningModelId, 1);
        }
      }
    },
    [activeId, getKnownSession, onModelLoveScoreChange, persistSessionSnapshot, updateRound],
  );

  const stop = useCallback(() => {
    abortStreams();
    const streamingSessionId = streamingSessionIdRef.current;
    if (streamingSessionId !== null) {
      const updated = markStoppedSession(streamingSessionId);
      if (updated) {
        persistSessionSnapshot(updated.session, updated.revision);
      }
    }
    streamingSessionIdRef.current = null;
    setIsStreaming(false);
  }, [abortStreams, markStoppedSession, persistSessionSnapshot]);

  const send = useCallback(async () => {
    const prompt = draft.trim();
    const files = draftFiles;
    if ((!prompt && files.length === 0) || isStreaming) {
      return;
    }
    if (userId === null) {
      setError("请先登录后再使用 Battle。");
      return;
    }

    setError(null);

    const pair = chooseModels(files);
    if (!pair) {
      return;
    }

    const [firstModel, secondModel] = pair;
    const targetActiveId = activeId;
    let baseSession = targetActiveId === null ? null : getKnownSession(targetActiveId);
    if (targetActiveId !== null && !baseSession) {
      try {
        const loadedSession = await fetchBattleSession(targetActiveId);
        if (activeIdRef.current !== targetActiveId) {
          return;
        }
        commitSession(loadedSession);
        baseSession = loadedSession;
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Battle 会话加载失败。");
        return;
      }
    }

    const promptLabel = prompt || attachmentPromptLabel(files);
    const nextTitle =
      baseSession && baseSession.rounds.length > 0
        ? baseSession.title
        : deriveConversationTitle(promptLabel, 0);

    // 这里先只把轮次骨架写进数据库，真正的附件 URL 要等流式接口返回服务端媒体地址。
    const round = createBattleRound({
      attachments: [],
      firstModel,
      prompt: promptLabel,
      secondModel,
    });

    setIsStreaming(true);

    try {
      let session: BattleSessionDetail;
      if (baseSession === null) {
        session = await createBattleSession({
          title: nextTitle,
          rounds: [round],
        });
        activeIdRef.current = session.id;
        setActiveId(session.id);
        setActiveSession(session);
      } else {
        session = await updateBattleSession(baseSession.id, {
          title: nextTitle,
          rounds: [...baseSession.rounds, round],
        });
      }
      commitSession(session);
      streamingSessionIdRef.current = session.id;
      setDraft("");
      onDraftAccepted?.();

      // Battle 真正开始发起后再通知宠物，避免未通过校验的提交也触发动画。
      onPetEvent?.("send");

      // 每个 side 都只继承自己之前的结果，避免把对手答案泄露给另一条流。
      const existingRounds = session.rounds.slice(0, -1);
      const buildSideHistory = (sideId: "a" | "b"): Array<{ role: string; content: string }> => {
        const history: Array<{ role: string; content: string }> = [];
        for (const existingRound of existingRounds) {
          const side = existingRound.sides[sideId];
          if (side.status !== "done" && side.status !== "error") {
            continue;
          }
          history.push({ role: "user", content: existingRound.prompt });
          history.push({
            role: "assistant",
            content: side.status === "error" ? side.error || "生成出错" : side.content,
          });
        }
        return history;
      };

      const controllers = [new AbortController(), new AbortController()];
      abortControllersRef.current = controllers;

      async function runSide(sideId: "a" | "b", modelOption: ModelOption, controller: AbortController) {
        const startedAt = Date.now();
        let usageCounted = false;
        const markUsageCounted = () => {
          if (usageCounted) {
            return;
          }
          usageCounted = true;
          // 中文注释：Battle 两侧各是一次独立模型调用，完成或报错时都即时同步调用数。
          onModelUsageCountChange?.(modelOption.id, 1);
        };

        try {
          await streamBattleResponse(
            {
              message: prompt,
              files,
              knowledge_folders: knowledgeFolders,
              model: modelOption.id,
              reasoning_profile: reasoningRequestValueForModel(
                modelOption,
                resolveModelDefaultReasoningProfile(modelOption),
              ),
              tool_mode: toolMode,
              history: buildSideHistory(sideId),
            },
            {
              signal: controller.signal,
              onEvent: (event) => {
                if (event.type === "attachments") {
                  const updated = updateRound(session.id, round.id, (currentRound) => ({
                    ...currentRound,
                    attachments: event.attachments,
                  }));
                  if (updated) {
                    persistSessionSnapshot(updated.session, updated.revision);
                  }
                  return;
                }

                if (event.type === "token") {
                  updateRound(
                    session.id,
                    round.id,
                    (currentRound) => ({
                      ...currentRound,
                      sides: {
                        ...currentRound.sides,
                        [sideId]: {
                          ...currentRound.sides[sideId],
                          content: currentRound.sides[sideId].content + event.content,
                        },
                      },
                    }),
                    { touchUpdatedAt: false },
                  );
                  return;
                }

                if (event.type === "reasoning") {
                  updateRound(
                    session.id,
                    round.id,
                    (currentRound) => ({
                      ...currentRound,
                      sides: {
                        ...currentRound.sides,
                        [sideId]: {
                          ...currentRound.sides[sideId],
                          reasoning: currentRound.sides[sideId].reasoning + event.content,
                        },
                      },
                    }),
                    { touchUpdatedAt: false },
                  );
                  return;
                }

                if (event.type === "done") {
                  markUsageCounted();
                  const updated = updateRound(session.id, round.id, (currentRound) => ({
                    ...currentRound,
                    sides: {
                      ...currentRound.sides,
                      [sideId]: {
                        ...currentRound.sides[sideId],
                        content:
                          typeof event.content === "string"
                            ? event.content
                            : currentRound.sides[sideId].content,
                        status: typeof event.content === "string" ? "done" : "error",
                        error:
                          typeof event.content === "string"
                            ? null
                            : "Battle 响应缺少完成内容。",
                        finishedAt: Date.now(),
                        startedAt,
                      },
                    },
                  }));
                  if (updated) {
                    persistSessionSnapshot(updated.session, updated.revision);
                  }
                  return;
                }

                if (event.type === "error") {
                  markUsageCounted();
                  const updated = updateRound(session.id, round.id, (currentRound) => ({
                    ...currentRound,
                    sides: {
                      ...currentRound.sides,
                      [sideId]: {
                        ...currentRound.sides[sideId],
                        status: "error",
                        error: event.message,
                        finishedAt: Date.now(),
                        startedAt,
                      },
                    },
                  }));
                  if (updated) {
                    persistSessionSnapshot(updated.session, updated.revision);
                  }
                }
              },
            },
          );
        } catch (streamError) {
          if (controller.signal.aborted) {
            return;
          }

          markUsageCounted();
          const updated = updateRound(session.id, round.id, (currentRound) => ({
            ...currentRound,
            sides: {
              ...currentRound.sides,
              [sideId]: {
                ...currentRound.sides[sideId],
                status: "error",
                error: streamError instanceof Error ? streamError.message : String(streamError),
                finishedAt: Date.now(),
                startedAt,
              },
            },
          }));
          if (updated) {
            persistSessionSnapshot(updated.session, updated.revision);
          }
        }
      }

      await Promise.all([
        runSide("a", firstModel, controllers[0]),
        runSide("b", secondModel, controllers[1]),
      ]);
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : "Battle 创建失败。");
    } finally {
      abortControllersRef.current = [];
      streamingSessionIdRef.current = null;
      setIsStreaming(false);
    }
  }, [
    activeId,
    chooseModels,
    commitSession,
    draft,
    draftFiles,
    getKnownSession,
    isStreaming,
    knowledgeFolders,
    onDraftAccepted,
    onModelUsageCountChange,
    onPetEvent,
    setError,
    toolMode,
    updateRound,
    userId,
  ]);

  const rename = useCallback(async (sessionId: number, title: string) => {
    const nextTitle = title.trim();
    if (!nextTitle) {
      return;
    }

    try {
      const summary = await renameBattleSession(sessionId, nextTitle);
      upsertSessionSummary(summary);
      updateKnownSession(sessionId, (session) => ({
        ...session,
        title: summary.title,
        updated_at: summary.updated_at,
      }));
    } catch (renameError) {
      setError(renameError instanceof Error ? renameError.message : "Battle 重命名失败。");
    }
  }, [setError, updateKnownSession, upsertSessionSummary]);

  const remove = useCallback(
    async (sessionId: number) => {
      try {
        if (streamingSessionIdRef.current === sessionId) {
          abortStreams();
          streamingSessionIdRef.current = null;
          setIsStreaming(false);
        }

        if (activeIdRef.current === sessionId) {
          loadAbortRef.current?.abort();
        }

        await deleteBattleSession(sessionId);
        sessionCacheRef.current.delete(sessionId);
        sessionRevisionRef.current.delete(sessionId);
        removeSessionSummary(sessionId);

        if (activeIdRef.current === sessionId) {
          activeIdRef.current = null;
          setActiveId(null);
          setActiveSession(null);
          setDraft("");
        }
      } catch (deleteError) {
        setError(deleteError instanceof Error ? deleteError.message : "Battle 删除失败。");
      }
    },
    [abortStreams, removeSessionSummary, setError],
  );

  return {
    activeId,
    activeSession,
    draft,
    filteredSessions,
    isLoading: activeId !== null && activeSession === null,
    isStreaming,
    loaded: sessionsLoaded,
    abortStreams,
    clearActiveSession,
    remove,
    rename,
    selectSession,
    send,
    setDraft,
    startNewSession,
    stop,
    vote,
  };
}
