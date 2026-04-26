import {
  startTransition,
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useLatestRequestGuard } from "../../../shared/hooks/useLatestRequestGuard";
import {
  ASSISTANT_DRAFT_ID,
  deriveConversationTitle,
  INITIAL_CHAT_MODEL,
  pickLandingTitle,
} from "../../chats/lib/constants";
import { resolveImageGenerationSize } from "../../chats/lib/imageSizeOptions";
import {
  appendRetryDraft,
  createAssistantDraftMessageForModel,
  createTransientAttachments,
  createUserDraftMessage,
  labelForStage,
  mergeConversationWithCache,
  restoreAttachmentFiles,
  stageForToolMode,
} from "../../chats/lib/chatSessionUtils";
import { useAudioRecorder } from "../../chats/model/useAudioRecorder";
import { useComposerAttachments } from "../../chats/model/useComposerAttachments";
import { useConversationStreams } from "../../chats/model/useConversationStreams";
import { useKnowledgeManager } from "../../knowledge/model/useKnowledgeManager";
import { useMemoryManager } from "../../memories/model/useMemoryManager";
import { fetchModels } from "../../models/api/models";
import {
  deleteConversation,
  fetchConversation,
  fetchConversationMessages,
  fetchConversations,
  renameConversation,
  updateMessageFeedback,
} from "../../chats/api/conversations";
import { generateImage } from "../../chats/api/generateImage";
import { regenerateChat, streamActiveChat, streamChat } from "../../chats/api/streamChat";
import {
  createDebateSession,
  deleteDebateSession,
  fetchDebateSession,
  fetchDebateSessions,
  renameDebateSession,
} from "../../debates/api/debates";
import { applyStreamEvent } from "../../debates/lib/debateRoomUtils";
import {
  createInitialModelOptions,
  createModelOption,
  ensureSelectedModel,
  findModelOption,
  resolveInitialSelectedModel,
} from "../../models/lib/modelOptions";
import {
  normalizeReasoningProfileForModel,
  reasoningRequestValueForModel,
  resolveModelDefaultReasoningProfile,
  resolveModelReasoningControl,
} from "../../models/lib/reasoningProfiles";
import type { WorkspaceSection } from "./workspaceSections";
import { transcribeAudio } from "../../../lib/api";
import { ApiError } from "../../../shared/api/http";
import { buildConversationMarkdown, buildDebateMarkdown, downloadMarkdown } from "../../../lib/exportMarkdown";
import type {
  AudioTranscriptionResult,
  DebateAiSuggestion,
  ChatMessage,
  ComposerMode,
  ConversationDetail,
  ConversationSummary,
  DebateSessionDetail,
  DebateSessionSummary,
  DebateStreamEvent,
  ModelOption,
  ReasoningProfileValue,
  ToolMode,
} from "../../../types";

type UseChatAppOptions = {
  closeMobileSidebar: () => void;
  isDesktop: boolean;
  onSectionRouteChange?: (section: WorkspaceSection) => void;
  routeSection?: WorkspaceSection;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
};

type DebateTransientState = {
  aiSuggestion: DebateAiSuggestion | null;
  judgeAnalysisStream: string;
  runKey: string | null;
  lastSeq: number | null;
};

const CONVERSATION_VIEW_MESSAGE_LIMIT = 24;
const CONVERSATION_EXPORT_MESSAGE_LIMIT = 100;
const ACTIVE_CHAT_CONVERSATION_CACHE_STORAGE_KEY = "chatchat.active-chat-conversations";
const DEBATE_TRANSIENT_STATE_STORAGE_KEY = "chatchat.debate-transient-states";
const DEFAULT_IMAGE_SIZE = "1024x1024";

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

function toggleToolMode(current: ToolMode, next: Exclude<ToolMode, "none">): ToolMode {
  return current === next ? "none" : next;
}

function mergeDraftWithTranscript(current: string, transcript: string): string {
  const normalizedTranscript = transcript.trim();
  if (!normalizedTranscript) {
    return current;
  }

  if (!current.trim()) {
    return normalizedTranscript;
  }

  const suffix = current.endsWith("\n") ? "" : "\n";
  return `${current}${suffix}${normalizedTranscript}`;
}

const MIN_RELIABLE_TRANSCRIPTION_DURATION_MS = 300;
const MEANINGFUL_TRANSCRIPT_PATTERN = /[\u3400-\u9fffA-Za-z0-9]/;

function shouldIgnoreLowConfidenceTranscript(result: AudioTranscriptionResult): boolean {
  const text = result.text.trim();
  if (!text) {
    return true;
  }

  const compactText = text.replace(/\s+/g, "");
  if (result.duration_ms > 0 && result.duration_ms < MIN_RELIABLE_TRANSCRIPTION_DURATION_MS) {
    return compactText.length <= 1;
  }

  return compactText.length <= 3 && !MEANINGFUL_TRANSCRIPT_PATTERN.test(compactText);
}

function emptyTranscriptionMessage(result: AudioTranscriptionResult): string | null {
  if (result.text.trim()) {
    return null;
  }

  switch (result.reason) {
    case "too_short":
      return "录音时间太短，请说完整一句后再松开。";
    case "too_quiet":
      return "录音音量太低，请靠近麦克风再试。";
    case "empty_audio":
      return "未捕获到有效音频，请检查麦克风权限后重试。";
    case "empty_transcript":
    default:
      return "没有识别到语音内容，请再说一次。";
  }
}

function debateActivityVersion(session: Pick<DebateSessionSummary, "updated_at" | "status" | "stage">) {
  return `${session.updated_at ?? "none"}:${session.status}:${session.stage}`;
}

function debateSessionRunKey(session: Pick<DebateSessionDetail, "id" | "active_run"> | null | undefined) {
  if (!session?.active_run) {
    return null;
  }

  return `${session.id}:${session.active_run.action}:${session.active_run.started_at ?? "none"}`;
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

export function useChatApp({
  closeMobileSidebar,
  isDesktop,
  onSectionRouteChange,
  routeSection = "chats",
  sidebarOpen,
  toggleSidebar,
}: UseChatAppOptions) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationsLoaded, setConversationsLoaded] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [activeConversation, setActiveConversation] = useState<ConversationDetail | null>(null);
  const [debateSessions, setDebateSessions] = useState<DebateSessionSummary[]>([]);
  const [debateSessionsLoaded, setDebateSessionsLoaded] = useState(false);
  const [activeDebateId, setActiveDebateId] = useState<number | null>(null);
  const [activeDebate, setActiveDebate] = useState<DebateSessionDetail | null>(null);
  const [debateTransientStates, setDebateTransientStates] = useState<Record<number, DebateTransientState>>(
    () => loadStoredDebateTransientStates(),
  );
  const [seenDebateUpdates, setSeenDebateUpdates] = useState<Record<number, string>>({});
  const [debateActivityOverrides, setDebateActivityOverrides] = useState<
    Record<number, { running: boolean; unread: boolean }>
  >({});
  const [debateCreateOpen, setDebateCreateOpen] = useState(false);
  const [activeSection, setActiveSection] = useState<WorkspaceSection>(routeSection);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [editingUserMessageId, setEditingUserMessageId] = useState<number | string | null>(null);
  const [editingUserMessageContent, setEditingUserMessageContent] = useState("");
  const [earlierMessagesError, setEarlierMessagesError] = useState<string | null>(null);
  const [models, setModels] = useState<ModelOption[]>(() => createInitialModelOptions());
  const [selectedModel, setSelectedModel] = useState(INITIAL_CHAT_MODEL);
  const [composerMode, setComposerModeState] = useState<ComposerMode>("chat");
  const [imageSize, setImageSize] = useState(DEFAULT_IMAGE_SIZE);
  const [reasoningProfile, setReasoningProfile] = useState<ReasoningProfileValue>("off");
  const [collapsedMessageIds, setCollapsedMessageIds] = useState<Set<number | string>>(new Set());
  const [toolMode, setToolMode] = useState<ToolMode>("none");
  const [landingHeroAnimated, setLandingHeroAnimated] = useState(false);
  const [landingTitle] = useState(() => pickLandingTitle());
  const [error, setError] = useState<string | null>(null);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isLoadingEarlierMessages, setIsLoadingEarlierMessages] = useState(false);
  const memoryManager = useMemoryManager({
    activeConversationId: activeConversationId && activeConversationId > 0 ? activeConversationId : null,
    enabled: activeSection === "memories",
  });
  const knowledgeManager = useKnowledgeManager({ enabled: activeSection === "knowledge" });
  const { addAttachments, clearAttachments, draftAttachments, removeAttachment, replaceAttachments } =
    useComposerAttachments();
  const { cancelRecording, isRecording, recordingError, startRecording, stopRecording } =
    useAudioRecorder();
  const transientAttachmentUrlsRef = useRef<string[]>([]);
  const composerModeRef = useRef<ComposerMode>("chat");
  const chatModelBeforeImageRef = useRef(INITIAL_CHAT_MODEL);
  const conversationLoadAbortRef = useRef<AbortController | null>(null);
  const earlierMessagesAbortRef = useRef<AbortController | null>(null);
  const debateLoadAbortRef = useRef<AbortController | null>(null);
  const chatConversationCacheRef = useRef<Record<number, ConversationDetail>>(
    loadStoredChatConversationCache(),
  );
  const debateSessionCacheRef = useRef<Map<number, DebateSessionDetail>>(new Map());
  const conversationLoadGuard = useLatestRequestGuard();
  const conversationsRefreshGuard = useLatestRequestGuard();
  const debatesRefreshGuard = useLatestRequestGuard();
  const debateLoadGuard = useLatestRequestGuard();
  const modelsLoadGuard = useLatestRequestGuard();
  const deferredQuery = useDeferredValue(query);
  const reasoningSyncKeyRef = useRef<string | null>(null);
  const previousRouteSectionRef = useRef(routeSection);

  const selectedModelOption = useMemo(
    () => findModelOption(models, selectedModel),
    [models, selectedModel],
  );
  const syncDebateRunningOverride = useCallback(
    (sessionId: number, activeRun: DebateSessionDetail["active_run"]) => {
      setDebateActivityOverrides((current) => {
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
    },
    [],
  );
  const attachmentUploadAvailable = selectedModelOption.supports_attachment_upload;
  const selectedModelReasoningKey = useMemo(
    () =>
      [
        selectedModelOption.id,
        resolveModelReasoningControl(selectedModelOption),
        resolveModelDefaultReasoningProfile(selectedModelOption),
      ].join(":"),
    [selectedModelOption],
  );
  const activeReasoningRequest = useMemo(
    () => reasoningRequestValueForModel(selectedModelOption, reasoningProfile),
    [reasoningProfile, selectedModelOption],
  );

  const clearTransientAttachmentUrls = useCallback(() => {
    transientAttachmentUrlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    transientAttachmentUrlsRef.current = [];
  }, []);

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
      // Ignore storage failures; the in-memory stream state still keeps the UI live.
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
    setActiveConversation,
    setActiveConversationId,
    setConversations,
    setError,
    setSelectedModel,
  });
  const submitBlocked = composerMode === "image" && draftAttachments.length > 0;
  const submitBlockedReason = submitBlocked ? "生成图片暂不支持附件，请先移除附件。" : null;

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
  }, [activeConversationId]);

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
        setActiveDebateId(null);
        setActiveDebate(null);
        setDebateCreateOpen(false);
        setCollapsedMessageIds(new Set());
        return;
      }
    });
  }, [routeSection]);

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
                  onEvent({
                    type: "reasoning",
                    content: lastAssistant.reasoning,
                  });
                }
                if (lastAssistant?.sources?.length) {
                  onEvent({
                    type: "sources",
                    sources: lastAssistant.sources,
                  });
                }
                if (lastAssistant?.context) {
                  onEvent({
                    type: "context",
                    context: lastAssistant.context,
                  });
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
        if (controller.signal.aborted) {
          return;
        }
        if (!conversationLoadGuard.isCurrent(requestId)) {
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
      setError,
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

  const loadDebateSession = useCallback(
    async (sessionId: number) => {
      const requestId = debateLoadGuard.begin();
      debateLoadAbortRef.current?.abort();
      const cachedSession = debateSessionCacheRef.current.get(sessionId);
      if (cachedSession) {
        setActiveDebate(cachedSession);
      }

      const controller = new AbortController();
      debateLoadAbortRef.current = controller;

      try {
        const session = mergeDebateSessionWithCache(
          await fetchDebateSession(sessionId),
          debateSessionCacheRef.current.get(sessionId),
        );
        if (!debateLoadGuard.isCurrent(requestId)) {
          return;
        }
        debateSessionCacheRef.current.set(session.id, session);
        setActiveDebate(session);
        syncDebateRunningOverride(session.id, session.active_run);
      } catch (loadError) {
        if (controller.signal.aborted) {
          return;
        }
        if (!debateLoadGuard.isCurrent(requestId)) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Failed to load debate session.");
      } finally {
        if (debateLoadAbortRef.current === controller) {
          debateLoadAbortRef.current = null;
        }
      }
    },
    [debateLoadGuard, setError, syncDebateRunningOverride],
  );

  const filteredConversations = useMemo(() => {
    if (!deferredQuery.trim()) {
      return conversations;
    }

    const keyword = deferredQuery.toLowerCase();
    return conversations.filter((item) => item.title.toLowerCase().includes(keyword));
  }, [conversations, deferredQuery]);

  const filteredDebateSessions = useMemo(() => {
    if (!deferredQuery.trim()) {
      return debateSessions;
    }

    const keyword = deferredQuery.toLowerCase();
    return debateSessions.filter((item) => item.topic.toLowerCase().includes(keyword));
  }, [debateSessions, deferredQuery]);

  useEffect(() => {
    if (debateSessions.length === 0) {
      return;
    }

    setSeenDebateUpdates((current) => {
      let changed = false;
      const next = { ...current };

      for (const session of debateSessions) {
        if (next[session.id] !== undefined) {
          continue;
        }

        next[session.id] = debateActivityVersion(session);
        changed = true;
      }

      return changed ? next : current;
    });
  }, [debateSessions]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    try {
      window.sessionStorage.setItem(
        DEBATE_TRANSIENT_STATE_STORAGE_KEY,
        JSON.stringify(debateTransientStates),
      );
    } catch {
      // Ignore storage failures; debate transient state should still work in memory.
    }
  }, [debateTransientStates]);

  const debateActivity = useMemo(() => {
    const base = Object.fromEntries(
      debateSessions.map((session) => [
        session.id,
        {
          running: false,
          unread:
            session.id !== activeDebateId &&
            seenDebateUpdates[session.id] !== debateActivityVersion(session),
        },
      ]),
    ) as Record<number, { running: boolean; unread: boolean }>;

    return {
      ...base,
      ...debateActivityOverrides,
    };
  }, [activeDebateId, debateActivityOverrides, debateSessions, seenDebateUpdates]);

  useEffect(() => {
    if (activeSection !== "debates" || !activeDebate) {
      return;
    }

    const nextVersion = debateActivityVersion(activeDebate);
    setSeenDebateUpdates((current) =>
      current[activeDebate.id] === nextVersion
        ? current
        : {
            ...current,
            [activeDebate.id]: nextVersion,
          },
    );
  }, [activeDebate, activeSection]);

  const availableModels = useMemo(
    () => ensureSelectedModel(models, selectedModel),
    [models, selectedModel],
  );

  const refreshConversations = useCallback(async () => {
    const requestId = conversationsRefreshGuard.begin();
    try {
      const items = await fetchConversations();
      if (!conversationsRefreshGuard.isCurrent(requestId)) {
        return;
      }
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
  }, [conversationsRefreshGuard, mergeConversationSummariesWithSessions, setError]);

  const refreshDebateSessions = useCallback(async () => {
    const requestId = debatesRefreshGuard.begin();
    try {
      const items = await fetchDebateSessions();
      if (!debatesRefreshGuard.isCurrent(requestId)) {
        return;
      }
      setDebateSessions(items);
    } catch (refreshError) {
      if (debatesRefreshGuard.isCurrent(requestId)) {
        setError(refreshError instanceof Error ? refreshError.message : "Failed to refresh debates.");
      }
    } finally {
      if (debatesRefreshGuard.isCurrent(requestId)) {
        setDebateSessionsLoaded(true);
      }
    }
  }, [debatesRefreshGuard, setError]);

  const loadModels = useCallback(async () => {
    const requestId = modelsLoadGuard.begin();
    try {
      const payload = await fetchModels();
      if (!modelsLoadGuard.isCurrent(requestId)) {
        return;
      }
      const nextModels =
        payload.models.length > 0 ? payload.models : [createModelOption(payload.default_model)];
      setModels(nextModels);
      setSelectedModel(resolveInitialSelectedModel(nextModels, payload.default_model));
    } catch (loadError) {
      if (modelsLoadGuard.isCurrent(requestId)) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load models.");
      }
    }
  }, [modelsLoadGuard, setError]);

  useEffect(() => {
    void refreshConversations();
    void refreshDebateSessions();
    void loadModels();
  }, [loadModels, refreshConversations, refreshDebateSessions]);

  useEffect(() => {
    if (activeConversationId === null) {
      return;
    }

    void loadConversation(activeConversationId);
  }, [activeConversationId, loadConversation]);

  useEffect(() => {
    if (activeDebateId === null) {
      return;
    }

    void loadDebateSession(activeDebateId);
  }, [activeDebateId, loadDebateSession]);

  useEffect(() => {
    return () => {
      conversationLoadAbortRef.current?.abort();
      earlierMessagesAbortRef.current?.abort();
      debateLoadAbortRef.current?.abort();
      clearTransientAttachmentUrls();
    };
  }, [clearTransientAttachmentUrls]);

  useEffect(() => {
    if (reasoningSyncKeyRef.current === selectedModelReasoningKey) {
      return;
    }
    reasoningSyncKeyRef.current = selectedModelReasoningKey;
    setReasoningProfile(
      normalizeReasoningProfileForModel(
        selectedModelOption,
        resolveModelDefaultReasoningProfile(selectedModelOption),
      ),
    );
  }, [selectedModelOption, selectedModelReasoningKey]);

  useEffect(() => {
    if (!error) {
      return;
    }

    const timeoutId = window.setTimeout(() => setError(null), 5000);
    return () => window.clearTimeout(timeoutId);
  }, [error]);

  useEffect(() => {
    if (!recordingError) {
      return;
    }
    setError(recordingError);
  }, [recordingError]);

  const handleModelChange = useCallback((model: string) => {
    setSelectedModel(model);
  }, []);

  const setComposerModeValue = useCallback((mode: ComposerMode) => {
    composerModeRef.current = mode;
    setComposerModeState(mode);
  }, []);

  const restoreChatComposerMode = useCallback(() => {
    setComposerModeValue("chat");
    setSelectedModel(chatModelBeforeImageRef.current);
  }, [setComposerModeValue]);

  const handleComposerModeChange = useCallback(
    (mode: ComposerMode) => {
      if (mode === "image") {
        chatModelBeforeImageRef.current = selectedModel;
        setComposerModeValue("image");
        return;
      }
      restoreChatComposerMode();
    },
    [restoreChatComposerMode, selectedModel, setComposerModeValue],
  );

  const handleReasoningProfileChange = useCallback((value: ReasoningProfileValue) => {
    setReasoningProfile(normalizeReasoningProfileForModel(selectedModelOption, value));
  }, [selectedModelOption]);

  const handleStartRecording = useCallback(async () => {
    if (isStreaming || isTranscribing) {
      return;
    }

    try {
      await startRecording();
    } catch (recordingStartError) {
      const message =
        recordingStartError instanceof Error
          ? recordingStartError.message
          : "Failed to start audio recording.";
      setError(message);
    }
  }, [isStreaming, isTranscribing, setError, startRecording]);

  const handleStopRecording = useCallback(async () => {
    if (!isRecording || isTranscribing) {
      return;
    }

    setIsTranscribing(true);
    try {
      setError(null);
      const capture = await stopRecording();
      if (!capture.audioBlob) {
        setError("未捕获到有效音频，请检查 Edge 麦克风权限后重试。");
        return;
      }

      const result = await transcribeAudio(capture.audioBlob);
      const emptyMessage = emptyTranscriptionMessage(result);
      if (emptyMessage) {
        setError(emptyMessage);
        return;
      }
      if (shouldIgnoreLowConfidenceTranscript(result)) {
        setError("没有识别到可靠语音内容，请再说一次。");
        return;
      }
      setDraft((current) => mergeDraftWithTranscript(current, result.text));
      setError(null);
    } catch (transcriptionError) {
      const message =
        transcriptionError instanceof Error
          ? transcriptionError.message
          : "Failed to transcribe audio.";
      setError(message);
    } finally {
      setIsTranscribing(false);
    }
  }, [isRecording, isTranscribing, setError, stopRecording]);

  const handleToggleRecording = useCallback(() => {
    if (isRecording) {
      void handleStopRecording();
      return;
    }
    void handleStartRecording();
  }, [handleStartRecording, handleStopRecording, isRecording]);

  const handleNewChat = useCallback(() => {
    onSectionRouteChange?.("chats");
    cancelRecording();
    conversationLoadAbortRef.current?.abort();
    earlierMessagesAbortRef.current?.abort();
    debateLoadAbortRef.current?.abort();
    clearAttachments();
    startTransition(() => {
      setActiveSection("chats");
      setActiveConversationId(null);
      setActiveConversation(null);
      setActiveDebateId(null);
      setActiveDebate(null);
      setDebateCreateOpen(false);
      setCollapsedMessageIds(new Set());
      setDraft("");
      setError(null);
      if (!isDesktop) {
        closeMobileSidebar();
      }
    });
  }, [cancelRecording, clearAttachments, closeMobileSidebar, isDesktop, onSectionRouteChange]);

  const handleSelectConversation = useCallback(
    (conversationId: number) => {
      onSectionRouteChange?.("chats");
      cancelRecording();
      earlierMessagesAbortRef.current?.abort();
      debateLoadAbortRef.current?.abort();
      startTransition(() => {
        setActiveSection("chats");
        setActiveConversationId(conversationId);
        setActiveDebateId(null);
        setActiveDebate(null);
        setDebateCreateOpen(false);
        setError(null);
        setCollapsedMessageIds(new Set());
        openSessionConversation(conversationId);

        if (!isDesktop) {
          closeMobileSidebar();
        }
      });
    },
    [cancelRecording, closeMobileSidebar, isDesktop, onSectionRouteChange, openSessionConversation],
  );

  const handleNewDebate = useCallback(() => {
    cancelRecording();
    conversationLoadAbortRef.current?.abort();
    earlierMessagesAbortRef.current?.abort();
    debateLoadAbortRef.current?.abort();
    clearAttachments();
    startTransition(() => {
      setActiveSection("debates");
      setActiveConversationId(null);
      setActiveConversation(null);
      setActiveDebateId(null);
      setActiveDebate(null);
      setDebateCreateOpen(true);
      setCollapsedMessageIds(new Set());
      setDraft("");
      setError(null);
      if (!isDesktop) {
        closeMobileSidebar();
      }
    });
  }, [cancelRecording, clearAttachments, closeMobileSidebar, isDesktop]);

  const handleSelectDebate = useCallback(
    (sessionId: number) => {
      cancelRecording();
      earlierMessagesAbortRef.current?.abort();
      conversationLoadAbortRef.current?.abort();
      const cachedSession = debateSessionCacheRef.current.get(sessionId) ?? null;
      const knownSession = cachedSession ?? debateSessions.find((item) => item.id === sessionId) ?? null;
      startTransition(() => {
        setActiveSection("debates");
        setActiveConversationId(null);
        setActiveConversation(null);
        setActiveDebateId(sessionId);
        setActiveDebate(cachedSession);
        setDebateCreateOpen(false);
        if (knownSession) {
          const nextVersion = debateActivityVersion(knownSession);
          setSeenDebateUpdates((current) =>
            current[sessionId] === nextVersion
              ? current
              : {
                  ...current,
                  [sessionId]: nextVersion,
                },
          );
        }
        setError(null);
        setCollapsedMessageIds(new Set());

        if (!isDesktop) {
          closeMobileSidebar();
        }
      });
    },
    [cancelRecording, closeMobileSidebar, debateSessions, isDesktop],
  );

  const handleCreateDebate = useCallback(
    async (payload: {
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
    }) => {
      try {
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
        debateSessionCacheRef.current.set(created.id, created);
        setActiveSection("debates");
        setDebateCreateOpen(false);
        setActiveDebateId(created.id);
        setActiveDebate(created);
        setSeenDebateUpdates((current) => ({
          ...current,
          [created.id]: debateActivityVersion(created),
        }));
        void refreshDebateSessions();
        if (!isDesktop) {
          closeMobileSidebar();
        }
      } catch (createError) {
        setError(createError instanceof Error ? createError.message : "Failed to create debate.");
      }
    },
    [closeMobileSidebar, isDesktop, refreshDebateSessions],
  );

  const handleSelectSection = useCallback(
    (section: WorkspaceSection) => {
      onSectionRouteChange?.(section);
      startTransition(() => {
        setActiveSection(section);
        if (section === "chats") {
          setActiveConversationId(null);
          setActiveConversation(null);
          setActiveDebateId(null);
          setActiveDebate(null);
          setDebateCreateOpen(false);
          setCollapsedMessageIds(new Set());
          return;
        }
        if (section === "debates") {
          setActiveConversationId(null);
          setActiveConversation(null);
          setActiveDebateId(null);
          setActiveDebate(null);
          setDebateCreateOpen(true);
          setCollapsedMessageIds(new Set());
        }
      });
      if (!isDesktop) {
        closeMobileSidebar();
      }
    },
    [closeMobileSidebar, isDesktop, onSectionRouteChange],
  );

  const handleRenameConversation = useCallback(
    async (conversationId: number, title: string) => {
      await renameConversation(conversationId, title);
      setActiveConversation((current) =>
        current && current.id === conversationId ? { ...current, title } : current,
      );
      renameSession(conversationId, title);
      await refreshConversations();
    },
    [refreshConversations, renameSession],
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
      setError,
    ],
  );

  const handleRenameDebate = useCallback(
    async (sessionId: number, topic: string) => {
      await renameDebateSession(sessionId, topic);
      setActiveDebate((current) =>
        current && current.id === sessionId ? { ...current, topic } : current,
      );
      await refreshDebateSessions();
    },
    [refreshDebateSessions],
  );

  const handleDeleteDebate = useCallback(
    async (sessionId: number) => {
      try {
        await deleteDebateSession(sessionId);
        debateSessionCacheRef.current.delete(sessionId);
        setDebateTransientStates((current) => {
          if (!(sessionId in current)) {
            return current;
          }

          const { [sessionId]: _removed, ...rest } = current;
          return rest;
        });
        setSeenDebateUpdates((current) => {
          if (!(sessionId in current)) {
            return current;
          }

          const { [sessionId]: _removed, ...rest } = current;
          return rest;
        });
        await refreshDebateSessions();

        if (activeDebateId === sessionId) {
          setActiveDebateId(null);
          setActiveDebate(null);
          setDebateCreateOpen(true);
        }
      } catch (deleteError) {
        setError(deleteError instanceof Error ? deleteError.message : "Failed to delete debate.");
      }
    },
    [activeDebateId, refreshDebateSessions, setError],
  );

  const handleRefreshDebate = useCallback(
    async (sessionId: number) => {
      const refreshed = mergeDebateSessionWithCache(
        await fetchDebateSession(sessionId),
        debateSessionCacheRef.current.get(sessionId),
      );
      debateSessionCacheRef.current.set(sessionId, refreshed);
      syncDebateRunningOverride(sessionId, refreshed.active_run);
      setActiveDebate((current) => (current && current.id === sessionId ? refreshed : current));
      await refreshDebateSessions();
      return refreshed;
    },
    [refreshDebateSessions, syncDebateRunningOverride],
  );

  const handleSyncDebate = useCallback(
    (session: DebateSessionDetail) => {
      debateSessionCacheRef.current.set(session.id, session);
      if (session.judge_decision) {
        setDebateTransientStates((current) => {
          if (!(session.id in current)) {
            return current;
          }

          const { [session.id]: _removed, ...rest } = current;
          return rest;
        });
      }
      syncDebateRunningOverride(session.id, session.active_run);
      setActiveDebate((current) => (current && current.id === session.id ? session : current));
      void refreshDebateSessions();
    },
    [refreshDebateSessions, syncDebateRunningOverride],
  );

  const handleDebateTransientStateChange = useCallback(
    (
      sessionId: number,
      patch: Partial<DebateTransientState> | null,
    ) => {
      setDebateTransientStates((current) => {
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
    },
    [],
  );

  const handleDebateSnapshot = useCallback((session: DebateSessionDetail) => {
    debateSessionCacheRef.current.set(session.id, session);
    setActiveDebate((current) => (current && current.id === session.id ? session : current));
  }, []);

  const handleDebateStreamEvent = useCallback(
    (sessionId: number, event: DebateStreamEvent) => {
      const baseSession =
        debateSessionCacheRef.current.get(sessionId)
        ?? (activeDebate && activeDebate.id === sessionId ? activeDebate : null);
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
      debateSessionCacheRef.current.set(sessionId, nextSession);
      setActiveDebate((current) => (current && current.id === sessionId ? nextSession : current));
    },
    [activeDebate],
  );

  const handleDebateActivityChange = useCallback(
    (sessionId: number, nextActivity: { running: boolean; unread: boolean }) => {
      setDebateActivityOverrides((current) => {
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
    },
    [],
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
      if (controller.signal.aborted) {
        return;
      }
      setEarlierMessagesError(
        loadError instanceof Error ? loadError.message : "Failed to load earlier messages.",
      );
    } finally {
      if (earlierMessagesAbortRef.current === controller) {
        earlierMessagesAbortRef.current = null;
      }
      setIsLoadingEarlierMessages(false);
    }
  }, [activeConversation, isLoadingEarlierMessages, setError]);

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

  const handleExportItem = useCallback(
    async (itemId: number, kind: "chat" | "debate") => {
      try {
        if (kind === "debate") {
          const session = await fetchDebateSession(itemId);
          debateSessionCacheRef.current.set(session.id, session);
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
    [loadFullConversationForExport, setError],
  );

  const handleSend = useCallback(async () => {
    const message = draft.trim();
    const pendingFiles = draftAttachments.map((attachment) => attachment.file);
    const effectiveComposerMode = composerModeRef.current;
    if ((!message && pendingFiles.length === 0) || isRecording || isStreaming || isTranscribing) {
      return;
    }
    if (effectiveComposerMode === "image") {
      if (!message || pendingFiles.length > 0) {
        return;
      }

      const conversationModel = activeConversation?.model ?? chatModelBeforeImageRef.current;
      const imageGenerationSize = resolveImageGenerationSize(imageSize);
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
            title: deriveConversationTitle(message, 0),
            model: conversationModel,
            total_message_count: 2,
            loaded_message_count: 2,
            remaining_message_count: 0,
            messages: [tempUserMessage, createAssistantDraftMessageForModel(conversationModel)],
          };

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
          generateImage(
            {
              conversation_id:
                activeConversation && activeConversation.id > 0 ? activeConversation.id : null,
              prompt: message,
              size: imageGenerationSize,
            },
            { onEvent, signal },
          ),
      });

      if (result === "completed") {
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
          title: deriveConversationTitle(message, tempAttachments.length),
          model: effectiveModel,
          total_message_count: 2,
          loaded_message_count: 2,
          remaining_message_count: 0,
          messages: [tempUserMessage, createAssistantDraftMessageForModel(effectiveModel)],
        };

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
            message,
            files: pendingFiles,
            model: effectiveModel,
            reasoning_profile: effectiveReasoningProfile,
            tool_mode: toolMode,
          },
          { onEvent, signal },
        ),
    });

    if (result === "completed") {
      await refreshConversations();
    }
  }, [
    activeConversation,
    activeReasoningRequest,
    clearAttachments,
    composerMode,
    draft,
    draftAttachments,
    imageSize,
    isRecording,
    isStreaming,
    isTranscribing,
    refreshConversations,
    restoreChatComposerMode,
    toolMode,
    runStream,
    selectedModel,
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
  }, [activeConversation, draft, replaceAttachments, stopStream]);

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
                reasoning_profile: effectiveReasoningProfile,
                tool_mode: toolMode,
              },
              { onEvent, signal },
            );
          }

          const restoredFiles = await restoreAttachmentFiles(sourceUser.attachments ?? []);
          return streamChat(
            {
              conversation_id: activeConversation.id > 0 ? activeConversation.id : null,
              message: nextContent,
              files: restoredFiles,
              model: effectiveModel,
              reasoning_profile: effectiveReasoningProfile,
              tool_mode: toolMode,
            },
            { onEvent, signal },
          );
        },
      });

      if (result === "completed") {
        await refreshConversations();
      }
    },
    [
      activeConversation,
      activeReasoningRequest,
      isStreaming,
      refreshConversations,
      runStream,
      selectedModel,
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
    [
      activeConversation,
      isStreaming,
      startRegeneratedBranch,
    ],
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
    [activeConversation, isStreaming],
  );

  const handleCancelEditingUserMessage = useCallback(() => {
    setEditingUserMessageId(null);
    setEditingUserMessageContent("");
  }, []);

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
      startRegeneratedBranch,
    ],
  );

  const handleMessageFeedback = useCallback(async (messageId: number, value: "up" | "down" | null) => {
    try {
      await updateMessageFeedback(messageId, value);
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
  }, [setError]);

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
  const showSessionHeaderActions =
    activeSection === "chats" || activeSection === "debates";
  const showChatModelSelector = activeSection === "chats" && composerMode !== "image";

  return {
    activeSection,
    error,
    debateCreateProps: debateCreateOpen
      ? {
          defaultProModelId: selectedModel,
          defaultConModelId: selectedModel,
          models: availableModels,
          onCancel: () => setDebateCreateOpen(false),
          onCreate: handleCreateDebate,
        }
      : null,
    debateRoomProps: activeDebate
      ? {
          isSessionRunning: debateActivity[activeDebate.id]?.running ?? false,
          session: activeDebate,
          transientState: activeDebate ? (debateTransientStates[activeDebate.id] ?? null) : null,
          onRefresh: handleRefreshDebate,
          onActivityChange: handleDebateActivityChange,
          onSessionSnapshot: handleDebateSnapshot,
          onTransientStateChange: handleDebateTransientStateChange,
          onStreamEvent: handleDebateStreamEvent,
          onSessionChange: handleSyncDebate,
        }
      : null,
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
          imageSize,
          reserveThinkingSpace: activeReasoningRequest !== null && activeReasoningRequest !== "off",
          reasoningProfile,
          onChangeDraft: setDraft,
          onComposerModeChange: handleComposerModeChange,
          onImageSizeChange: setImageSize,
          onFeedback: (messageId: number, value: "up" | "down" | null) =>
            void handleMessageFeedback(messageId, value),
          onLoadEarlierMessages: () => void handleLoadEarlierMessages(),
          onModelChange: handleModelChange,
          onReasoningProfileChange: handleReasoningProfileChange,
          onCancelEditingUserMessage: handleCancelEditingUserMessage,
          onChangeEditingUserMessage: setEditingUserMessageContent,
          onRemoveDraftAttachment: removeAttachment,
          onRetry: handleRetryAssistant,
          onStartEditingUserMessage: handleStartEditingUserMessage,
          onSubmitEditingUserMessage: (messageId: number | string) => void handleSubmitEditedUserMessage(messageId),
          onSelectAttachments: addAttachments,
          onNewDebate: handleNewDebate,
          onSend: () => void handleSend(),
          onStop: handleStop,
          onToggleRecording: handleToggleRecording,
          onToggleRag: handleSelectRag,
          onToggleWeb: handleSelectWeb,
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
              ? ("debate" as const)
              : null
            : activeConversationId !== null
              ? ("chat" as const)
              : null
          : null,
      activeItemTitle: activeDebate?.topic ?? activeConversation?.title ?? "",
      isDesktop,
      mobileModel: showChatModelSelector ? selectedModel : "",
      mobileModels: showChatModelSelector ? availableModels : [],
      onNewChat: handleNewChat,
      onNewDebate: handleNewDebate,
      onDeleteItem: async (itemId: number, kind: "chat" | "debate") => {
        if (kind === "debate") {
          await handleDeleteDebate(itemId);
          return;
        }
        await handleDeleteConversation(itemId);
      },
      onExportItem: async (itemId: number, kind: "chat" | "debate") => {
        await handleExportItem(itemId, kind);
      },
      onRenameItem: async (itemId: number, title: string, kind: "chat" | "debate") => {
        if (kind === "debate") {
          await handleRenameDebate(itemId, title);
          return;
        }
        await handleRenameConversation(itemId, title);
      },
      onMobileModelChange: showChatModelSelector ? handleModelChange : undefined,
      onToggleSidebar: toggleSidebar,
      showTitle: true,
      sidebarOpen,
      title: "Chatchat",
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
      imageSize,
      reasoningProfile,
      onAnimationComplete: handleLandingAnimationComplete,
      onChangeDraft: setDraft,
      onComposerModeChange: handleComposerModeChange,
      onImageSizeChange: setImageSize,
      onModelChange: handleModelChange,
      onReasoningProfileChange: handleReasoningProfileChange,
      onRemoveDraftAttachment: removeAttachment,
      onSelectAttachments: addAttachments,
      onNewDebate: handleNewDebate,
      onSend: () => void handleSend(),
      onStop: handleStop,
      onToggleRecording: handleToggleRecording,
      onToggleRag: handleSelectRag,
      onToggleWeb: handleSelectWeb,
      toolMode,
      submitBlocked,
      submitBlockedReason,
      shouldAnimate: !landingHeroAnimated,
      title: landingTitle,
    },
    knowledgePageProps: {
      knowledge: knowledgeManager,
    },
    memoriesPageProps: {
      activeConversationId: activeConversationId && activeConversationId > 0 ? activeConversationId : null,
      activeConversationTitle: activeConversation?.title ?? "",
      memories: memoryManager,
    },
    modelsPageProps: {
      models: availableModels,
      onSelectModel: handleModelChange,
      selectedModel,
    },
    isConversationLoading: activeConversationId !== null && activeConversation === null,
    isDebateLoading: activeDebateId !== null && activeDebate === null,
    showLanding,
    sidebarProps: {
      activeSection,
      activeConversationId,
      activeDebateId,
      activity: conversationActivity,
      debateActivity,
      conversationsLoaded,
      debatesLoaded: debateSessionsLoaded,
      isDesktop,
      items: filteredConversations,
      debateItems: filteredDebateSessions,
      onSelectSection: handleSelectSection,
      onDelete: handleDeleteConversation,
      onDeleteDebate: handleDeleteDebate,
      onNewChat: handleNewChat,
      onNewDebate: handleNewDebate,
      onQueryChange: setQuery,
      onRename: handleRenameConversation,
      onRenameDebate: handleRenameDebate,
      onSelect: handleSelectConversation,
      onSelectDebate: handleSelectDebate,
      onToggleSidebar: toggleSidebar,
      open: sidebarOpen,
      query,
    },
  };
}
