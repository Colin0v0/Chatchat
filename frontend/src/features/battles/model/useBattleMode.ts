import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { readBrowserCache, writeBrowserCache, isRecord } from "../../../shared/lib/browserCache";
import { deriveConversationTitle } from "../../chats/lib/constants";
import { isModelOption } from "../../models/lib/modelOptionGuards";
import {
  reasoningRequestValueForModel,
  resolveModelDefaultReasoningProfile,
} from "../../models/lib/reasoningProfiles";
import { streamBattleResponse } from "../api/battle";
import type { BattleRound, BattleSessionDetail, BattleVote } from "./types";
import type { BattleSessionSummary, MessageAttachment, ModelOption, ToolMode } from "../../../types";

const BATTLE_SESSIONS_STORAGE_KEY_PREFIX = "chatchat.battle-sessions.v1";
const BATTLE_SESSION_CACHE_TTL_MS = 30 * 24 * 60 * 60 * 1000;

function getBattleSessionsStorageKey(userId: number | null): string {
  if (userId === null) {
    return `${BATTLE_SESSIONS_STORAGE_KEY_PREFIX}.anonymous`;
  }
  return `${BATTLE_SESSIONS_STORAGE_KEY_PREFIX}.${userId}`;
}

interface UseBattleModeOptions {
  availableModels: ModelOption[];
  draftFiles: File[];
  knowledgeFolders: string[];
  onDraftAccepted?: () => void;
  query: string;
  setError: (message: string | null) => void;
  toolMode: ToolMode;
  userId: number | null;
}

function isBattleSideState(value: unknown): value is BattleRound["sides"]["a"] {
  return (
    isRecord(value)
    && (value.id === "a" || value.id === "b")
    && isModelOption(value.model)
    && typeof value.content === "string"
    && typeof value.reasoning === "string"
    && (value.status === "streaming" || value.status === "done" || value.status === "error")
    && (typeof value.error === "string" || value.error === null)
    && typeof value.startedAt === "number"
    && (typeof value.finishedAt === "number" || value.finishedAt === null)
  );
}

function isBattleRound(value: unknown): value is BattleRound {
  return (
    isRecord(value)
    && typeof value.id === "string"
    && typeof value.prompt === "string"
    && typeof value.createdAt === "string"
    && typeof value.revealed === "boolean"
    && (value.vote === "a" || value.vote === "b" || value.vote === "both_good" || value.vote === "both_bad" || value.vote === null)
    && isRecord(value.sides)
    && isBattleSideState(value.sides.a)
    && isBattleSideState(value.sides.b)
  );
}

function isBattleSessionDetail(value: unknown): value is BattleSessionDetail {
  return (
    isRecord(value)
    && typeof value.id === "number"
    && typeof value.title === "string"
    && typeof value.created_at === "string"
    && (typeof value.updated_at === "string" || value.updated_at === null)
    && Array.isArray(value.rounds)
    && value.rounds.every(isBattleRound)
  );
}

function loadStoredBattleSessions(userId: number | null): BattleSessionDetail[] {
  return readBrowserCache(
    getBattleSessionsStorageKey(userId),
    (value): value is BattleSessionDetail[] => Array.isArray(value) && value.every(isBattleSessionDetail),
  ) ?? [];
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

export function useBattleMode({
  availableModels,
  draftFiles,
  knowledgeFolders,
  onDraftAccepted,
  query,
  setError,
  toolMode,
  userId,
}: UseBattleModeOptions) {
  const [sessions, setSessions] = useState<BattleSessionDetail[]>(() => loadStoredBattleSessions(userId));
  const [activeId, setActiveId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllersRef = useRef<AbortController[]>([]);
  const previousUserIdRef = useRef<number | null>(userId);

  const summaries = useMemo(
    () => sessions.map(battleSessionSummary),
    [sessions],
  );

  const filteredSessions = useMemo(() => {
    if (!query.trim()) {
      return summaries;
    }

    const keyword = query.toLowerCase();
    return summaries.filter((item) => item.title.toLowerCase().includes(keyword));
  }, [query, summaries]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeId) ?? null,
    [activeId, sessions],
  );

  useEffect(() => {
    // Battle 评测记录先保存在浏览器缓存里，侧边栏 Recents 直接读取这份本地会话。
    const timeoutId = window.setTimeout(() => {
      writeBrowserCache(getBattleSessionsStorageKey(userId), sessions, BATTLE_SESSION_CACHE_TTL_MS);
    }, 400);
    return () => window.clearTimeout(timeoutId);
  }, [sessions, userId]);

  useEffect(() => {
    if (previousUserIdRef.current !== userId) {
      previousUserIdRef.current = userId;
      abortStreams();
      setIsStreaming(false);
      setActiveId(null);
      setDraft("");
      setSessions(loadStoredBattleSessions(userId));
    }
  }, [userId]);

  const abortStreams = useCallback(() => {
    abortControllersRef.current.forEach((controller) => controller.abort());
    abortControllersRef.current = [];
  }, []);

  const startNewSession = useCallback(() => {
    setActiveId(null);
    setDraft("");
  }, []);

  const selectSession = useCallback((sessionId: number) => {
    setActiveId(sessionId);
  }, []);

  const clearActiveSession = useCallback(() => {
    setActiveId(null);
  }, []);

  const updateRound = useCallback(
    (
      sessionId: number,
      roundId: string,
      update: (round: BattleRound) => BattleRound,
    ) => {
      const updatedAt = new Date().toISOString();
      setSessions((current) =>
        current.map((session) =>
          session.id === sessionId
            ? {
                ...session,
                updated_at: updatedAt,
                rounds: session.rounds.map((round) => (round.id === roundId ? update(round) : round)),
              }
            : session,
        ),
      );
    },
    [],
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

  const vote = useCallback(
    (roundId: string, nextVote: BattleVote) => {
      if (activeId === null) {
        return;
      }
      updateRound(activeId, roundId, (round) => ({
        ...round,
        revealed: true,
        vote: nextVote,
      }));
    },
    [activeId, updateRound],
  );

  const stop = useCallback(() => {
    abortStreams();
    if (activeId !== null) {
      const stoppedAt = Date.now();
      const updatedAt = new Date(stoppedAt).toISOString();
      setSessions((current) =>
        current.map((session) => {
          if (session.id !== activeId) {
            return session;
          }

          const latestRoundIndex = session.rounds.length - 1;
          return {
            ...session,
            updated_at: updatedAt,
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
        }),
      );
    }
    setIsStreaming(false);
  }, [abortStreams, activeId]);

  const send = useCallback(async () => {
    const prompt = draft.trim();
    const files = draftFiles;
    if ((!prompt && files.length === 0) || isStreaming) {
      return;
    }

    const pair = chooseModels(files);
    if (!pair) {
      return;
    }

    const [firstModel, secondModel] = pair;
    const now = new Date().toISOString();
    const promptLabel = prompt || attachmentPromptLabel(files);
    const attachments: MessageAttachment[] = files.map((file) => ({
      id: `battle-attach-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      kind: file.type.startsWith("image/") ? "image" : "file",
      original_name: file.name,
      mime_type: file.type,
      size_bytes: file.size,
      extension: file.name.includes(".") ? file.name.slice(file.name.lastIndexOf(".")) : undefined,
      url: URL.createObjectURL(file),
    }));
    const round = createBattleRound({
      attachments,
      firstModel,
      prompt: promptLabel,
      secondModel,
    });
    const sessionId = activeId ?? Date.now();
    const nextTitle = deriveConversationTitle(promptLabel, 0);
    const nextSession: BattleSessionDetail = {
      id: sessionId,
      title: nextTitle,
      created_at: now,
      updated_at: now,
      rounds: [round],
    };

    // 构建每 side 的历史上下文：只包含当前 session 中已完成的轮次
    const existingRounds = activeSession?.rounds ?? [];
    const buildSideHistory = (sideId: "a" | "b"): Array<{ role: string; content: string }> => {
      const history: Array<{ role: string; content: string }> = [];
      for (const r of existingRounds) {
        const side = r.sides[sideId];
        if (side.status !== "done" && side.status !== "error") {
          continue;
        }
        history.push({ role: "user", content: r.prompt });
        history.push({
          role: "assistant",
          content: side.status === "error" ? side.error || "生成出错" : side.content,
        });
      }
      return history;
    };

    setDraft("");
    onDraftAccepted?.();
    setIsStreaming(true);
    setActiveId(sessionId);
    setSessions((current) => {
      const existing = current.find((session) => session.id === sessionId);
      if (!existing) {
        return [nextSession, ...current];
      }
      return current.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              updated_at: now,
              rounds: [...session.rounds, round],
            }
          : session,
      );
    });

    const controllers = [new AbortController(), new AbortController()];
    abortControllersRef.current = controllers;

    async function runSide(sideId: "a" | "b", modelOption: ModelOption, controller: AbortController) {
      const startedAt = Date.now();
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
                updateRound(sessionId, round.id, (currentRound) => ({
                  ...currentRound,
                  attachments: event.attachments,
                }));
                return;
              }
              if (event.type === "token") {
                updateRound(sessionId, round.id, (currentRound) => ({
                  ...currentRound,
                  sides: {
                    ...currentRound.sides,
                    [sideId]: {
                      ...currentRound.sides[sideId],
                      content: currentRound.sides[sideId].content + event.content,
                    },
                  },
                }));
                return;
              }
              if (event.type === "reasoning") {
                updateRound(sessionId, round.id, (currentRound) => ({
                  ...currentRound,
                  sides: {
                    ...currentRound.sides,
                    [sideId]: {
                      ...currentRound.sides[sideId],
                      reasoning: currentRound.sides[sideId].reasoning + event.content,
                    },
                  },
                }));
                return;
              }
              if (event.type === "done") {
                if (typeof event.content !== "string") {
                  updateRound(sessionId, round.id, (currentRound) => ({
                    ...currentRound,
                    sides: {
                      ...currentRound.sides,
                      [sideId]: {
                        ...currentRound.sides[sideId],
                        status: "error",
                        error: "Battle 响应缺少完成内容。",
                        finishedAt: Date.now(),
                        startedAt,
                      },
                    },
                  }));
                  return;
                }
                updateRound(sessionId, round.id, (currentRound) => ({
                  ...currentRound,
                  sides: {
                    ...currentRound.sides,
                    [sideId]: {
                      ...currentRound.sides[sideId],
                      content: event.content,
                      status: "done",
                      finishedAt: Date.now(),
                      startedAt,
                    },
                  },
                }));
                return;
              }
              if (event.type === "error") {
                updateRound(sessionId, round.id, (currentRound) => ({
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
              }
            },
          },
        );
      } catch (streamError) {
        if (controller.signal.aborted) {
          return;
        }
        updateRound(sessionId, round.id, (currentRound) => ({
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
      }
    }

    await Promise.all([
      runSide("a", firstModel, controllers[0]),
      runSide("b", secondModel, controllers[1]),
    ]);
    abortControllersRef.current = [];
    setIsStreaming(false);
  }, [
    activeId,
    activeSession,
    chooseModels,
    draft,
    draftFiles,
    isStreaming,
    knowledgeFolders,
    onDraftAccepted,
    toolMode,
    updateRound,
  ]);

  const rename = useCallback((sessionId: number, title: string) => {
    const nextTitle = title.trim();
    if (!nextTitle) {
      return;
    }

    const updatedAt = new Date().toISOString();
    setSessions((current) =>
      current.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              title: nextTitle,
              updated_at: updatedAt,
            }
          : session,
      ),
    );
  }, []);

  const remove = useCallback(
    (sessionId: number) => {
      if (activeId === sessionId) {
        abortStreams();
        setIsStreaming(false);
        setActiveId(null);
        setDraft("");
      }

      setSessions((current) => current.filter((session) => session.id !== sessionId));
    },
    [abortStreams, activeId],
  );

  return {
    activeId,
    activeSession,
    draft,
    filteredSessions,
    isStreaming,
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
