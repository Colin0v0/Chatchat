import { startTransition, useDeferredValue, useEffect, useRef, useState } from "react";

import { ConversationView } from "./components/ConversationView";
import { LandingView } from "./components/LandingView";
import { MainHeader } from "./components/MainHeader";
import { Sidebar } from "./components/Sidebar";
import {
  deleteConversation,
  fetchConversation,
  fetchConversations,
  fetchModels,
  regenerateChat,
  renameConversation,
  streamChat,
} from "./lib/api";
import type {
  ChatMessage,
  ChatStreamEvent,
  ConversationDetail,
  ConversationSummary,
  ModelOption,
} from "./types";

const ASSISTANT_DRAFT_ID = "assistant-draft";
const INITIAL_CHAT_MODEL = "openai:deepseek-chat";
const INITIAL_REASONING_MODEL = "openai:deepseek-reasoner";
const SIDEBAR_STORAGE_KEY = "chatchat:sidebar-state";
const LANDING_TITLES = [
  "你好同志，请问有什么需要帮助的吗？",
  "今天想让模型帮你做什么？",
  "这次想先解决哪个问题？",
  "给我一个目标，我来帮你拆。",
  "今天这件事，我们从哪一步开始？",
] as const;

function pickLandingTitle() {
  return LANDING_TITLES[Math.floor(Math.random() * LANDING_TITLES.length)];
}

type SidebarState = {
  desktopOpen: boolean;
  mobileOpen: boolean;
};

function getDefaultSidebarState(): SidebarState {
  return {
    desktopOpen: true,
    mobileOpen: false,
  };
}

function readSidebarState(): SidebarState {
  if (typeof window === "undefined") {
    return getDefaultSidebarState();
  }

  try {
    const raw = window.localStorage.getItem(SIDEBAR_STORAGE_KEY);
    if (!raw) {
      return getDefaultSidebarState();
    }

    const parsed = JSON.parse(raw) as Partial<SidebarState>;
    return {
      desktopOpen: parsed.desktopOpen ?? true,
      mobileOpen: parsed.mobileOpen ?? false,
    };
  } catch {
    return getDefaultSidebarState();
  }
}

function writeSidebarState(state: SidebarState) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(SIDEBAR_STORAGE_KEY, JSON.stringify(state));
}

function createFallbackModelOption(id: string): ModelOption {
  if (id === INITIAL_CHAT_MODEL) {
    return {
      id,
      label: "deepseek-chat",
      supports_thinking: true,
      supports_thinking_trace: false,
      chat_model: INITIAL_CHAT_MODEL,
      reasoning_model: INITIAL_REASONING_MODEL,
    };
  }

  if (id === INITIAL_REASONING_MODEL) {
    return {
      id,
      label: "deepseek-reasoner",
      supports_thinking: true,
      supports_thinking_trace: true,
      chat_model: INITIAL_CHAT_MODEL,
      reasoning_model: INITIAL_REASONING_MODEL,
    };
  }

  const separatorIndex = id.indexOf(":");
  return {
    id,
    label: separatorIndex > 0 ? id.slice(separatorIndex + 1) : id,
    supports_thinking: false,
    supports_thinking_trace: false,
    chat_model: null,
    reasoning_model: null,
  };
}

function createInitialModelOptions(): ModelOption[] {
  return [
    createFallbackModelOption(INITIAL_CHAT_MODEL),
    createFallbackModelOption(INITIAL_REASONING_MODEL),
  ];
}

function findModelOption(models: ModelOption[], modelId: string): ModelOption {
  return models.find((item) => item.id === modelId) ?? createFallbackModelOption(modelId);
}

function withSelectedModel(models: ModelOption[], modelId: string): ModelOption[] {
  if (!modelId || models.some((item) => item.id === modelId)) {
    return models;
  }
  return [...models, createFallbackModelOption(modelId)];
}

function resolveInitialSelectedModel(models: ModelOption[], preferredModel: string): string {
  const option = findModelOption(models, preferredModel);
  return option.reasoning_model ?? preferredModel;
}

export default function App() {
  const [sidebarState, setSidebarState] = useState<SidebarState>(() => readSidebarState());
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= 768);
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const desktop = window.innerWidth >= 768;
    const persisted = readSidebarState();
    return desktop ? persisted.desktopOpen : persisted.mobileOpen;
  });
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationsLoaded, setConversationsLoaded] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [activeConversation, setActiveConversation] = useState<ConversationDetail | null>(null);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [models, setModels] = useState<ModelOption[]>(() => createInitialModelOptions());
  const [selectedModel, setSelectedModel] = useState(INITIAL_REASONING_MODEL);
  const [collapsedMessageIds, setCollapsedMessageIds] = useState<Set<number | string>>(new Set());
  const [ragEnabled, setRagEnabled] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingReasoning, setStreamingReasoning] = useState("");
  const [thinkingExpanded, setThinkingExpanded] = useState(false);
  const [landingHeroAnimated, setLandingHeroAnimated] = useState(false);
  const [landingTitle] = useState(() => pickLandingTitle());
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastDesktopRef = useRef(window.innerWidth >= 768);
  const deferredQuery = useDeferredValue(query);
  const selectedModelOption = findModelOption(models, selectedModel);
  const thinkingAvailable = selectedModelOption.supports_thinking;
  const thinkingTraceAvailable = selectedModelOption.supports_thinking_trace;
  const thinkingEnabled =
    thinkingAvailable && selectedModelOption.reasoning_model === selectedModel;

  useEffect(() => {
    void refreshConversations();
    void loadModels();
  }, []);

  useEffect(() => {
    writeSidebarState(sidebarState);
  }, [sidebarState]);

  useEffect(() => {
    function syncViewportState() {
      const desktop = window.innerWidth >= 768;
      setIsDesktop(desktop);
      if (desktop !== lastDesktopRef.current) {
        setSidebarOpen(desktop ? sidebarState.desktopOpen : sidebarState.mobileOpen);
        lastDesktopRef.current = desktop;
      }
    }

    syncViewportState();
    window.addEventListener("resize", syncViewportState);
    return () => window.removeEventListener("resize", syncViewportState);
  }, [sidebarState.desktopOpen, sidebarState.mobileOpen]);

  useEffect(() => {
    if (activeConversationId === null || isStreaming) {
      return;
    }
    void loadConversation(activeConversationId);
  }, [activeConversationId, isStreaming]);

  async function refreshConversations() {
    try {
      const items = await fetchConversations();
      setConversations(items);
    } finally {
      setConversationsLoaded(true);
    }
  }

  async function loadModels() {
    const payload = await fetchModels();
    const nextModels =
      payload.models.length > 0
        ? payload.models
        : [createFallbackModelOption(payload.default_model)];
    setModels(nextModels);
    setSelectedModel(resolveInitialSelectedModel(nextModels, payload.default_model));
  }

  async function loadConversation(conversationId: number) {
    const conversation = await fetchConversation(conversationId);
    setActiveConversation(conversation);
    setSelectedModel(conversation.model);
  }

  function handleModelChange(model: string) {
    setSelectedModel(model);
  }

  function handleToggleThinking() {
    if (!thinkingAvailable) {
      return;
    }

    if (thinkingEnabled) {
      setSelectedModel(selectedModelOption.chat_model ?? selectedModel);
      return;
    }

    setSelectedModel(selectedModelOption.reasoning_model ?? selectedModel);
  }

  function handleNewChat() {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }

    startTransition(() => {
      setActiveConversationId(null);
      setActiveConversation(null);
      setCollapsedMessageIds(new Set());
      setDraft("");
      setError(null);
      setIsStreaming(false);
      setStreamingReasoning("");
      setThinkingExpanded(false);
      if (!isDesktop) {
        handleSetSidebarOpen(false, false);
      }
    });
  }

  function handleSelectConversation(conversationId: number) {
    startTransition(() => {
      setActiveConversationId(conversationId);
      setError(null);
      setCollapsedMessageIds(new Set());
      setStreamingReasoning("");
      setThinkingExpanded(false);
      if (!isDesktop) {
        handleSetSidebarOpen(false, false);
      }
    });
  }

  function handleSetSidebarOpen(nextOpen: boolean | ((current: boolean) => boolean), desktop = isDesktop) {
    setSidebarOpen((current) => {
      const resolved = typeof nextOpen === "function" ? nextOpen(current) : nextOpen;
      setSidebarState((previous) =>
        desktop
          ? { ...previous, desktopOpen: resolved }
          : { ...previous, mobileOpen: resolved },
      );
      return resolved;
    });
  }

  async function handleRenameConversation(conversationId: number, title: string) {
    await renameConversation(conversationId, title);
    await refreshConversations();
    if (activeConversationId === conversationId) {
      setActiveConversation((current) => (current ? { ...current, title } : current));
    }
  }

  async function handleDeleteConversation(conversationId: number) {
    await deleteConversation(conversationId);
    await refreshConversations();

    if (activeConversationId === conversationId) {
      setActiveConversationId(null);
      setActiveConversation(null);
      setCollapsedMessageIds(new Set());
      setDraft("");
    }
  }

  function upsertDraftMessage(content: string) {
    setActiveConversation((current) => {
      if (!current) {
        return null;
      }

      const messages = current.messages.filter((item) => item.id !== ASSISTANT_DRAFT_ID);
      const draftMessage: ChatMessage = {
        id: ASSISTANT_DRAFT_ID,
        role: "assistant",
        content,
      };

      return {
        ...current,
        messages: [...messages, draftMessage],
      };
    });
  }

  function startRetryDraft(content: string, messageId: number | string) {
    setActiveConversation((current) => {
      if (!current) {
        return null;
      }

      const messages = current.messages.filter((item) => item.id !== ASSISTANT_DRAFT_ID);
      return {
        ...current,
        messages: [
          ...messages,
          {
            id: messageId,
            role: "user",
            content,
            created_at: new Date().toISOString(),
          },
          { id: ASSISTANT_DRAFT_ID, role: "assistant", content: "" },
        ],
      };
    });
  }

  function replaceMessageId(fromId: number | string, toId: number | string) {
    setActiveConversation((current) => {
      if (!current) {
        return null;
      }

      return {
        ...current,
        messages: current.messages.map((item) =>
          item.id === fromId ? { ...item, id: toId } : item,
        ),
      };
    });
  }

  async function handleSend() {
    const message = draft.trim();
    if (!message || isStreaming) {
      return;
    }
    const effectiveModel = selectedModel;

    setDraft("");
    setError(null);
    setIsStreaming(true);
    setStreamingReasoning("");
    setThinkingExpanded(false);

    const tempUserMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: message,
      created_at: new Date().toISOString(),
    };

    setActiveConversation((current) => {
      if (current) {
        return {
          ...current,
          model: effectiveModel,
          messages: [
            ...current.messages,
            tempUserMessage,
            { id: ASSISTANT_DRAFT_ID, role: "assistant", content: "" },
          ],
        };
      }

      return {
        id: 0,
        title: message.slice(0, 48),
        model: effectiveModel,
        messages: [tempUserMessage, { id: ASSISTANT_DRAFT_ID, role: "assistant", content: "" }],
      };
    });

    const controller = new AbortController();
    abortRef.current = controller;
    let streamedConversationId = activeConversationId;

    try {
      await streamChat(
        {
          conversation_id: activeConversationId,
          message,
          model: effectiveModel,
        },
        {
          signal: controller.signal,
          onEvent: (event: ChatStreamEvent) => {
            if (event.type === "meta") {
              streamedConversationId = event.conversation_id;
              setActiveConversationId(event.conversation_id);
              setSelectedModel(event.model);
              return;
            }

            if (event.type === "token") {
              setActiveConversation((current) => {
                if (!current) {
                  return current;
                }

                return {
                  ...current,
                  messages: current.messages.map((item) =>
                    item.id === ASSISTANT_DRAFT_ID
                      ? { ...item, content: item.content + event.content }
                      : item,
                  ),
                };
              });
              return;
            }

            if (event.type === "reasoning") {
              setStreamingReasoning((current) => current + event.content);
              return;
            }

            if (event.type === "error") {
              setError(event.message);
              upsertDraftMessage(event.message);
            }
          },
        },
      );

      if (streamedConversationId !== null) {
        await loadConversation(streamedConversationId);
        await refreshConversations();
      }
    } catch (streamError) {
      if (streamError instanceof DOMException && streamError.name === "AbortError") {
        setError("生成已停止。");
      } else if (streamError instanceof Error) {
        setError(streamError.message);
      } else {
        setError("发送消息失败。");
      }
    } finally {
      setIsStreaming(false);
      setStreamingReasoning("");
      setThinkingExpanded(false);
      abortRef.current = null;
    }
  }

  function handleStop() {
    abortRef.current?.abort();
  }

  async function handleRetryAssistant(messageId: number) {
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

    const effectiveModel = selectedModel;
    const retryUserDraftId = `retry-user-${messageId}-${Date.now()}`;
    setError(null);
    setIsStreaming(true);
    setStreamingReasoning("");
    setThinkingExpanded(false);
    setCollapsedMessageIds((current) => new Set([...current, sourceUser.id, messageId]));
    startRetryDraft(sourceUser.content, retryUserDraftId);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await regenerateChat(
        {
          conversation_id: activeConversation.id,
          assistant_message_id: messageId,
          model: effectiveModel,
        },
        {
          signal: controller.signal,
          onEvent: (event: ChatStreamEvent) => {
            if (event.type === "meta") {
              setSelectedModel(event.model);
              replaceMessageId(retryUserDraftId, event.message_id);
              return;
            }

            if (event.type === "token") {
              setActiveConversation((current) => {
                if (!current) {
                  return current;
                }

                return {
                  ...current,
                  messages: current.messages.map((item) =>
                    item.id === ASSISTANT_DRAFT_ID
                      ? { ...item, content: item.content + event.content }
                      : item,
                  ),
                };
              });
              return;
            }

            if (event.type === "reasoning") {
              setStreamingReasoning((current) => current + event.content);
              return;
            }

            if (event.type === "done" && event.assistant_message_id != null) {
              const assistantMessageId = event.assistant_message_id;
              setActiveConversation((current) => {
                if (!current) {
                  return current;
                }

                return {
                  ...current,
                  messages: current.messages.map((item) =>
                    item.id === ASSISTANT_DRAFT_ID
                      ? { ...item, id: assistantMessageId }
                      : item,
                  ),
                };
              });
              return;
            }

            if (event.type === "error") {
              setError(event.message);
              upsertDraftMessage(event.message);
            }
          },
        },
      );

      await refreshConversations();
    } catch (streamError) {
      if (streamError instanceof DOMException && streamError.name === "AbortError") {
        setError("生成已停止。");
      } else if (streamError instanceof Error) {
        setError(streamError.message);
      } else {
        setError("重新生成失败。");
      }
    } finally {
      setIsStreaming(false);
      setStreamingReasoning("");
      setThinkingExpanded(false);
      abortRef.current = null;
    }
  }

  const filteredConversations = conversations.filter((item) => {
    if (!deferredQuery.trim()) {
      return true;
    }

    const keyword = deferredQuery.toLowerCase();
    return (
      item.title.toLowerCase().includes(keyword) ||
      item.last_message_preview.toLowerCase().includes(keyword)
    );
  });

  const availableModels = withSelectedModel(models, selectedModel);
  const hasConversation = Boolean(activeConversation && activeConversation.messages.length > 0);
  const headerTitle = "Chatchat";

  return (
    <div className="flex h-[100dvh] min-h-0 overflow-hidden bg-app-bg text-app-text">
      <Sidebar
        activeConversationId={activeConversationId}
        conversationsLoaded={conversationsLoaded}
        isDesktop={isDesktop}
        items={filteredConversations}
        onNewChat={handleNewChat}
        onDelete={handleDeleteConversation}
        onQueryChange={setQuery}
        onRename={handleRenameConversation}
        onSelect={handleSelectConversation}
        onToggleSidebar={() => handleSetSidebarOpen((value) => !value)}
        open={sidebarOpen}
        query={query}
      />

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-app-panel">
        <MainHeader
          conversationId={activeConversationId}
          conversationTitle={activeConversation?.title ?? ""}
          isDesktop={isDesktop}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
          onToggleSidebar={() => handleSetSidebarOpen((value) => !value)}
          showTitle
          sidebarOpen={sidebarOpen}
          title={headerTitle}
        />

        {!hasConversation || !activeConversation ? (
          <LandingView
            draft={draft}
            isStreaming={isStreaming}
            model={selectedModel}
            models={availableModels}
            onAnimationComplete={() => setLandingHeroAnimated(true)}
            onChangeDraft={setDraft}
            onModelChange={handleModelChange}
            onSend={() => void handleSend()}
            onStop={handleStop}
            onToggleRag={() => setRagEnabled((value) => !value)}
            onToggleThinking={handleToggleThinking}
            ragEnabled={ragEnabled}
            shouldAnimate={!landingHeroAnimated}
            thinkingAvailable={thinkingAvailable}
            thinkingEnabled={thinkingEnabled}
            title={landingTitle}
          />
        ) : (
          <ConversationView
            collapsedMessageIds={collapsedMessageIds}
            conversation={activeConversation}
            draft={draft}
            isStreaming={isStreaming}
            model={selectedModel}
            models={availableModels}
            onChangeDraft={setDraft}
            onModelChange={handleModelChange}
            onRetry={handleRetryAssistant}
            onSend={() => void handleSend()}
            onStop={handleStop}
            onToggleRag={() => setRagEnabled((value) => !value)}
            onToggleThinking={handleToggleThinking}
            onToggleThinkingTrace={() => setThinkingExpanded((value) => !value)}
            ragEnabled={ragEnabled}
            thinkingAvailable={thinkingAvailable}
            thinkingEnabled={thinkingEnabled}
            thinkingTrace={streamingReasoning}
            thinkingTraceAvailable={thinkingTraceAvailable}
            thinkingTraceExpanded={thinkingExpanded}
          />
        )}

        {error ? (
          <div className="fixed top-4 right-4 z-30 max-w-[420px] rounded-lg border border-black/10 bg-app-danger px-4 py-3 text-[14px] text-white md:top-6 md:right-6">
            {error}
          </div>
        ) : null}

        <div className="pointer-events-none px-4 pt-2 pb-2 text-center text-[13px] text-app-muted/80 md:px-6 md:pt-2 md:pb-2">
          Chatchat can make mistakes. Please verify important information.
        </div>
      </main>
    </div>
  );
}
