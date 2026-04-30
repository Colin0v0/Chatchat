import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useLatestRequestGuard } from "../../../shared/hooks/useLatestRequestGuard";
import {
  createDebateSession,
  deleteDebateSession,
  fetchDebateSession,
  fetchDebateSessions,
  renameDebateSession,
} from "../api/debates";
import { applyStreamEvent } from "../lib/debateRoomUtils";
import {
  loadStoredDebateSummariesCache,
  saveDebateSummariesCache,
} from "../../workspace/model/workspaceCache";
import type {
  DebateAiSuggestion,
  DebateSessionDetail,
  DebateSessionSummary,
  DebateStreamEvent,
} from "../../../types";

type DebateTransientState = {
  aiSuggestion: DebateAiSuggestion | null;
  judgeAnalysisStream: string;
  runKey: string | null;
  lastSeq: number | null;
};

interface DebateCreatePayload {
  topic: string;
  proModelId: string;
  conModelId: string;
  judgeModelId: string;
  proStyle: string;
  conStyle: string;
  openingDurationSec: number;
  rebuttalDurationSec: number;
  freeDebateDurationSec: number;
  closingDurationSec: number;
}

interface UseDebateModeOptions {
  query: string;
  setError: (message: string | null) => void;
}

const DEBATE_TRANSIENT_STATE_STORAGE_KEY = "chatchat.debate-transient-states";

function debateActivityVersion(session: Pick<DebateSessionSummary, "updated_at" | "status" | "stage">) {
  return `${session.updated_at ?? "none"}:${session.status}:${session.stage}`;
}

function debateSessionRunKey(session: Pick<DebateSessionDetail, "id" | "active_run"> | null | undefined) {
  if (!session?.active_run) {
    return null;
  }

  return `${session.id}:${session.active_run.action}:${session.active_run.started_at ?? "none"}`;
}

function loadStoredDebateTransientStates(): Record<number, DebateTransientState> {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    const raw = window.sessionStorage.getItem(DEBATE_TRANSIENT_STATE_STORAGE_KEY);
    if (!raw) {
      return {};
    }

    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      return {};
    }

    const next: Record<number, DebateTransientState> = {};
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      const sessionId = Number(key);
      if (!Number.isInteger(sessionId) || !value || typeof value !== "object") {
        continue;
      }

      const payload = value as Record<string, unknown>;
      next[sessionId] = {
        aiSuggestion:
          payload.aiSuggestion && typeof payload.aiSuggestion === "object"
            ? (payload.aiSuggestion as DebateAiSuggestion)
            : null,
        judgeAnalysisStream:
          typeof payload.judgeAnalysisStream === "string" ? payload.judgeAnalysisStream : "",
        runKey: typeof payload.runKey === "string" ? payload.runKey : null,
        lastSeq:
          typeof payload.lastSeq === "number" && Number.isFinite(payload.lastSeq)
            ? payload.lastSeq
            : null,
      };
    }

    return next;
  } catch {
    return {};
  }
}

function mergeDebateSessionWithCache(
  serverSession: DebateSessionDetail,
  cachedSession: DebateSessionDetail | null | undefined,
): DebateSessionDetail {
  if (!cachedSession || cachedSession.id !== serverSession.id) {
    return serverSession;
  }

  const serverRunKey = debateSessionRunKey(serverSession);
  const cachedRunKey = debateSessionRunKey(cachedSession);
  if (serverRunKey !== cachedRunKey) {
    return serverSession;
  }

  const cachedTurnsById = new Map(cachedSession.turns.map((turn) => [turn.id, turn]));
  const mergedTurns = serverSession.turns.map((turn) => {
    const cachedTurn = cachedTurnsById.get(turn.id);
    if (!cachedTurn) {
      return turn;
    }

    const serverContentLength = turn.content.trim().length;
    const cachedContentLength = cachedTurn.content.trim().length;
    const serverReasoningLength = (turn.reasoning ?? "").trim().length;
    const cachedReasoningLength = (cachedTurn.reasoning ?? "").trim().length;

    return {
      ...turn,
      content: cachedContentLength > serverContentLength ? cachedTurn.content : turn.content,
      reasoning: cachedReasoningLength > serverReasoningLength ? cachedTurn.reasoning : turn.reasoning,
      elapsed_ms: turn.elapsed_ms ?? cachedTurn.elapsed_ms ?? null,
      truncated: turn.truncated || cachedTurn.truncated === true,
    };
  });

  const knownTurnIds = new Set(mergedTurns.map((turn) => turn.id));
  const cachedOnlyTurns = cachedSession.turns.filter((turn) => !knownTurnIds.has(turn.id));

  return {
    ...serverSession,
    active_run: serverSession.active_run
      ? {
          ...serverSession.active_run,
          last_seq: Math.max(
            serverSession.active_run.last_seq ?? 0,
            cachedSession.active_run?.last_seq ?? 0,
          ) || null,
        }
      : serverSession.active_run,
    turns: [...mergedTurns, ...cachedOnlyTurns].sort((left, right) =>
      left.turn_index === right.turn_index
        ? String(left.created_at ?? "").localeCompare(String(right.created_at ?? ""))
        : left.turn_index - right.turn_index,
    ),
  };
}

export function useDebateMode({ query, setError }: UseDebateModeOptions) {
  const [initialDebateSummariesCache] = useState(() => loadStoredDebateSummariesCache());
  const [sessions, setSessions] = useState<DebateSessionSummary[]>(() => initialDebateSummariesCache ?? []);
  const [sessionsLoaded, setSessionsLoaded] = useState(() => initialDebateSummariesCache !== null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [activeSession, setActiveSession] = useState<DebateSessionDetail | null>(null);
  const [transientStates, setTransientStates] = useState<Record<number, DebateTransientState>>(
    () => loadStoredDebateTransientStates(),
  );
  const [seenUpdates, setSeenUpdates] = useState<Record<number, string>>({});
  const [activityOverrides, setActivityOverrides] = useState<Record<number, { running: boolean; unread: boolean }>>({});
  const [createOpen, setCreateOpen] = useState(false);
  const loadAbortRef = useRef<AbortController | null>(null);
  const sessionCacheRef = useRef<Map<number, DebateSessionDetail>>(new Map());
  const refreshGuard = useLatestRequestGuard();
  const loadGuard = useLatestRequestGuard();

  const syncRunningOverride = useCallback((sessionId: number, activeRun: DebateSessionDetail["active_run"]) => {
    setActivityOverrides((current) => {
      if (activeRun) {
        const previous = current[sessionId];
        if (previous?.running && previous.unread === false) {
          return current;
        }

        return {
          ...current,
          [sessionId]: {
            running: true,
            unread: false,
          },
        };
      }

      if (!current[sessionId]) {
        return current;
      }

      const { [sessionId]: _removed, ...rest } = current;
      return rest;
    });
  }, []);

  const filteredSessions = useMemo(() => {
    if (!query.trim()) {
      return sessions;
    }

    const keyword = query.toLowerCase();
    return sessions.filter((item) => item.topic.toLowerCase().includes(keyword));
  }, [query, sessions]);

  const activity = useMemo(() => {
    const base = Object.fromEntries(
      sessions.map((session) => [
        session.id,
        {
          running: false,
          unread:
            session.id !== activeId &&
            seenUpdates[session.id] !== debateActivityVersion(session),
        },
      ]),
    ) as Record<number, { running: boolean; unread: boolean }>;

    return {
      ...base,
      ...activityOverrides,
    };
  }, [activeId, activityOverrides, sessions, seenUpdates]);

  const refreshSessions = useCallback(async () => {
    const requestId = refreshGuard.begin();
    try {
      const items = await fetchDebateSessions();
      if (!refreshGuard.isCurrent(requestId)) {
        return;
      }
      saveDebateSummariesCache(items);
      setSessions(items);
    } catch (refreshError) {
      if (refreshGuard.isCurrent(requestId)) {
        setError(refreshError instanceof Error ? refreshError.message : "Failed to refresh debates.");
      }
    } finally {
      if (refreshGuard.isCurrent(requestId)) {
        setSessionsLoaded(true);
      }
    }
  }, [refreshGuard, setError]);

  const loadSession = useCallback(
    async (sessionId: number) => {
      const requestId = loadGuard.begin();
      loadAbortRef.current?.abort();
      const cachedSession = sessionCacheRef.current.get(sessionId);
      if (cachedSession) {
        setActiveSession(cachedSession);
      }

      const controller = new AbortController();
      loadAbortRef.current = controller;

      try {
        const session = mergeDebateSessionWithCache(
          await fetchDebateSession(sessionId),
          sessionCacheRef.current.get(sessionId),
        );
        if (!loadGuard.isCurrent(requestId)) {
          return;
        }
        sessionCacheRef.current.set(session.id, session);
        setActiveSession(session);
        syncRunningOverride(session.id, session.active_run);
      } catch (loadError) {
        if (controller.signal.aborted) {
          return;
        }
        if (!loadGuard.isCurrent(requestId)) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Failed to load debate session.");
      } finally {
        if (loadAbortRef.current === controller) {
          loadAbortRef.current = null;
        }
      }
    },
    [loadGuard, setError, syncRunningOverride],
  );

  useEffect(() => {
    void refreshSessions();
  }, [refreshSessions]);

  useEffect(() => {
    if (activeId === null) {
      return;
    }

    void loadSession(activeId);
  }, [activeId, loadSession]);

  useEffect(() => {
    if (sessions.length === 0) {
      return;
    }

    setSeenUpdates((current) => {
      let changed = false;
      const next = { ...current };

      for (const session of sessions) {
        if (next[session.id] !== undefined) {
          continue;
        }

        next[session.id] = debateActivityVersion(session);
        changed = true;
      }

      return changed ? next : current;
    });
  }, [sessions]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    try {
      window.sessionStorage.setItem(
        DEBATE_TRANSIENT_STATE_STORAGE_KEY,
        JSON.stringify(transientStates),
      );
    } catch {
      // 辩论运行态只是 UI 恢复数据，写入失败时保留内存态继续跑。
    }
  }, [transientStates]);

  useEffect(() => {
    return () => {
      loadAbortRef.current?.abort();
    };
  }, []);

  const markActiveSeen = useCallback((session: DebateSessionDetail | DebateSessionSummary) => {
    const nextVersion = debateActivityVersion(session);
    setSeenUpdates((current) =>
      current[session.id] === nextVersion
        ? current
        : {
            ...current,
            [session.id]: nextVersion,
          },
    );
  }, []);

  const clearActive = useCallback(() => {
    setActiveId(null);
    setActiveSession(null);
    setCreateOpen(false);
  }, []);

  const openCreate = useCallback(() => {
    setActiveId(null);
    setActiveSession(null);
    setCreateOpen(true);
  }, []);

  const selectSession = useCallback(
    (sessionId: number) => {
      const cachedSession = sessionCacheRef.current.get(sessionId) ?? null;
      const knownSession = cachedSession ?? sessions.find((item) => item.id === sessionId) ?? null;
      setActiveId(sessionId);
      setActiveSession(cachedSession);
      setCreateOpen(false);
      if (knownSession) {
        markActiveSeen(knownSession);
      }
    },
    [markActiveSeen, sessions],
  );

  const createSession = useCallback(
    async (payload: DebateCreatePayload) => {
      const created = await createDebateSession({
        topic: payload.topic,
        pro_model_id: payload.proModelId,
        con_model_id: payload.conModelId,
        judge_model_id: payload.judgeModelId,
        tool_mode: "none",
        pro_style: payload.proStyle,
        con_style: payload.conStyle,
        style: "",
        free_debate_enabled: true,
        opening_duration_sec: payload.openingDurationSec,
        rebuttal_duration_sec: payload.rebuttalDurationSec,
        free_debate_duration_sec: payload.freeDebateDurationSec,
        closing_duration_sec: payload.closingDurationSec,
      });
      sessionCacheRef.current.set(created.id, created);
      setCreateOpen(false);
      setActiveId(created.id);
      setActiveSession(created);
      setSeenUpdates((current) => ({
        ...current,
        [created.id]: debateActivityVersion(created),
      }));
      void refreshSessions();
      return created;
    },
    [refreshSessions],
  );

  const renameSession = useCallback(
    async (sessionId: number, topic: string) => {
      await renameDebateSession(sessionId, topic);
      setActiveSession((current) =>
        current && current.id === sessionId ? { ...current, topic } : current,
      );
      await refreshSessions();
    },
    [refreshSessions],
  );

  const deleteSession = useCallback(
    async (sessionId: number) => {
      try {
        await deleteDebateSession(sessionId);
        sessionCacheRef.current.delete(sessionId);
        setTransientStates((current) => {
          if (!(sessionId in current)) {
            return current;
          }

          const { [sessionId]: _removed, ...rest } = current;
          return rest;
        });
        setSeenUpdates((current) => {
          if (!(sessionId in current)) {
            return current;
          }

          const { [sessionId]: _removed, ...rest } = current;
          return rest;
        });
        await refreshSessions();

        if (activeId === sessionId) {
          setActiveId(null);
          setActiveSession(null);
          setCreateOpen(true);
        }
      } catch (deleteError) {
        setError(deleteError instanceof Error ? deleteError.message : "Failed to delete debate.");
      }
    },
    [activeId, refreshSessions, setError],
  );

  const refreshActiveSession = useCallback(
    async (sessionId: number) => {
      const refreshed = mergeDebateSessionWithCache(
        await fetchDebateSession(sessionId),
        sessionCacheRef.current.get(sessionId),
      );
      sessionCacheRef.current.set(sessionId, refreshed);
      syncRunningOverride(sessionId, refreshed.active_run);
      setActiveSession((current) => (current && current.id === sessionId ? refreshed : current));
      await refreshSessions();
      return refreshed;
    },
    [refreshSessions, syncRunningOverride],
  );

  const syncSession = useCallback(
    (session: DebateSessionDetail) => {
      sessionCacheRef.current.set(session.id, session);
      if (session.judge_decision) {
        setTransientStates((current) => {
          if (!(session.id in current)) {
            return current;
          }

          const { [session.id]: _removed, ...rest } = current;
          return rest;
        });
      }
      syncRunningOverride(session.id, session.active_run);
      setActiveSession((current) => (current && current.id === session.id ? session : current));
      void refreshSessions();
    },
    [refreshSessions, syncRunningOverride],
  );

  const updateTransientState = useCallback((sessionId: number, patch: Partial<DebateTransientState> | null) => {
    setTransientStates((current) => {
      if (patch == null) {
        if (!(sessionId in current)) {
          return current;
        }

        const { [sessionId]: _removed, ...rest } = current;
        return rest;
      }

      const previous = current[sessionId] ?? {
        aiSuggestion: null,
        judgeAnalysisStream: "",
        runKey: null,
        lastSeq: null,
      };
      const next = {
        ...previous,
        ...patch,
      };

      if (
        previous.aiSuggestion === next.aiSuggestion
        && previous.judgeAnalysisStream === next.judgeAnalysisStream
        && previous.runKey === next.runKey
        && previous.lastSeq === next.lastSeq
      ) {
        return current;
      }

      return {
        ...current,
        [sessionId]: next,
      };
    });
  }, []);

  const snapshotSession = useCallback((session: DebateSessionDetail) => {
    sessionCacheRef.current.set(session.id, session);
    setActiveSession((current) => (current && current.id === session.id ? session : current));
  }, []);

  const handleStreamEvent = useCallback(
    (sessionId: number, event: DebateStreamEvent) => {
      const baseSession =
        sessionCacheRef.current.get(sessionId)
        ?? (activeSession && activeSession.id === sessionId ? activeSession : null);
      if (!baseSession) {
        return;
      }

      let nextSession = applyStreamEvent(baseSession, event);
      if (
        nextSession.active_run
        && (
          (typeof event.run_id === "string" && event.run_id.trim())
          || (typeof event.seq === "number" && Number.isFinite(event.seq))
        )
      ) {
        nextSession = {
          ...nextSession,
          active_run: {
            ...nextSession.active_run,
            run_id:
              typeof event.run_id === "string" && event.run_id.trim()
                ? event.run_id.trim()
                : nextSession.active_run.run_id ?? null,
            last_seq: Math.max(nextSession.active_run.last_seq ?? 0, event.seq ?? 0) || null,
          },
        };
      }
      sessionCacheRef.current.set(sessionId, nextSession);
      setActiveSession((current) => (current && current.id === sessionId ? nextSession : current));
    },
    [activeSession],
  );

  const handleActivityChange = useCallback((sessionId: number, nextActivity: { running: boolean; unread: boolean }) => {
    setActivityOverrides((current) => {
      const previous = current[sessionId];

      if (nextActivity.running) {
        if (previous?.running && !previous.unread) {
          return current;
        }

        return {
          ...current,
          [sessionId]: {
            running: true,
            unread: false,
          },
        };
      }

      if (!previous) {
        return current;
      }

      const { [sessionId]: _removed, ...rest } = current;
      return rest;
    });
  }, []);

  const fetchSessionForExport = useCallback(async (sessionId: number) => {
    const session = await fetchDebateSession(sessionId);
    sessionCacheRef.current.set(session.id, session);
    return session;
  }, []);

  const roomProps = activeSession
    ? {
        isSessionRunning: activity[activeSession.id]?.running ?? false,
        session: activeSession,
        transientState: transientStates[activeSession.id] ?? null,
        onRefresh: refreshActiveSession,
        onActivityChange: handleActivityChange,
        onSessionSnapshot: snapshotSession,
        onTransientStateChange: updateTransientState,
        onStreamEvent: handleStreamEvent,
        onSessionChange: syncSession,
      }
    : null;

  return {
    activeId,
    activeSession,
    activity,
    createOpen,
    filteredSessions,
    isLoading: activeId !== null && activeSession === null,
    loaded: sessionsLoaded,
    roomProps,
    clearActive,
    createSession,
    deleteSession,
    fetchSessionForExport,
    markActiveSeen,
    openCreate,
    renameSession,
    selectSession,
  };
}
