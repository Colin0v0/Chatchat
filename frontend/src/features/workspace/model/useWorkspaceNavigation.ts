import {
  startTransition,
  useCallback,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from "react";

import type { WorkspaceSection } from "./workspaceSections";

interface UseWorkspaceNavigationOptions {
  cancelRecording: () => void;
  clearActiveBattleSession: () => void;
  clearActiveDebate: () => void;
  clearAttachments: () => void;
  closeMobileSidebar: () => void;
  conversationLoadAbortRef: MutableRefObject<AbortController | null>;
  createDebate: (payload: {
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
  }) => Promise<unknown>;
  earlierMessagesAbortRef: MutableRefObject<AbortController | null>;
  isDesktop: boolean;
  onSectionRouteChange?: (section: WorkspaceSection) => void;
  openDebateCreate: () => void;
  openSessionConversation: (conversationId: number) => void;
  selectBattleSession: (sessionId: number) => void;
  selectDebateSession: (sessionId: number) => void;
  setActiveConversation: Dispatch<SetStateAction<any>>;
  setActiveConversationId: Dispatch<SetStateAction<number | null>>;
  setActiveSection: Dispatch<SetStateAction<WorkspaceSection>>;
  setCollapsedMessageIds: Dispatch<SetStateAction<Set<number | string>>>;
  setDraft: Dispatch<SetStateAction<string>>;
  setError: Dispatch<SetStateAction<string | null>>;
  startNewBattleSession: () => void;
}

export function useWorkspaceNavigation({
  cancelRecording,
  clearActiveBattleSession,
  clearActiveDebate,
  clearAttachments,
  closeMobileSidebar,
  conversationLoadAbortRef,
  createDebate,
  earlierMessagesAbortRef,
  isDesktop,
  onSectionRouteChange,
  openDebateCreate,
  openSessionConversation,
  selectBattleSession,
  selectDebateSession,
  setActiveConversation,
  setActiveConversationId,
  setActiveSection,
  setCollapsedMessageIds,
  setDraft,
  setError,
  startNewBattleSession,
}: UseWorkspaceNavigationOptions) {
  const handleNewChat = useCallback(() => {
    onSectionRouteChange?.("chats");
    cancelRecording();
    conversationLoadAbortRef.current?.abort();
    earlierMessagesAbortRef.current?.abort();
    clearAttachments();
    startTransition(() => {
      setActiveSection("chats");
      setActiveConversationId(null);
      setActiveConversation(null);
      clearActiveDebate();
      clearActiveBattleSession();
      setCollapsedMessageIds(new Set());
      setDraft("");
      setError(null);
      if (!isDesktop) {
        closeMobileSidebar();
      }
    });
  }, [
    cancelRecording,
    clearActiveBattleSession,
    clearActiveDebate,
    clearAttachments,
    closeMobileSidebar,
    conversationLoadAbortRef,
    earlierMessagesAbortRef,
    isDesktop,
    onSectionRouteChange,
    setActiveConversation,
    setActiveConversationId,
    setActiveSection,
    setCollapsedMessageIds,
    setDraft,
    setError,
  ]);

  const handleSelectConversation = useCallback(
    (conversationId: number) => {
      onSectionRouteChange?.("chats");
      cancelRecording();
      earlierMessagesAbortRef.current?.abort();
      startTransition(() => {
        setActiveSection("chats");
        setActiveConversationId(conversationId);
        clearActiveDebate();
        clearActiveBattleSession();
        setError(null);
        setCollapsedMessageIds(new Set());
        openSessionConversation(conversationId);

        if (!isDesktop) {
          closeMobileSidebar();
        }
      });
    },
    [
      cancelRecording,
      clearActiveBattleSession,
      clearActiveDebate,
      closeMobileSidebar,
      earlierMessagesAbortRef,
      isDesktop,
      onSectionRouteChange,
      openSessionConversation,
      setActiveConversationId,
      setActiveSection,
      setCollapsedMessageIds,
      setError,
    ],
  );

  const handleNewDebate = useCallback(() => {
    cancelRecording();
    conversationLoadAbortRef.current?.abort();
    earlierMessagesAbortRef.current?.abort();
    clearAttachments();
    startTransition(() => {
      setActiveSection("debates");
      setActiveConversationId(null);
      setActiveConversation(null);
      openDebateCreate();
      clearActiveBattleSession();
      setCollapsedMessageIds(new Set());
      setDraft("");
      setError(null);
      if (!isDesktop) {
        closeMobileSidebar();
      }
    });
  }, [
    cancelRecording,
    clearActiveBattleSession,
    clearAttachments,
    closeMobileSidebar,
    conversationLoadAbortRef,
    earlierMessagesAbortRef,
    isDesktop,
    openDebateCreate,
    setActiveConversation,
    setActiveConversationId,
    setActiveSection,
    setCollapsedMessageIds,
    setDraft,
    setError,
  ]);

  const handleCancelCreateDebate = useCallback(() => {
    onSectionRouteChange?.("chats");
    startTransition(() => {
      setActiveSection("chats");
      setActiveConversationId(null);
      setActiveConversation(null);
      clearActiveDebate();
      setCollapsedMessageIds(new Set());
      setError(null);
    });
  }, [
    clearActiveDebate,
    onSectionRouteChange,
    setActiveConversation,
    setActiveConversationId,
    setActiveSection,
    setCollapsedMessageIds,
    setError,
  ]);

  const handleSelectDebate = useCallback(
    (sessionId: number) => {
      onSectionRouteChange?.("debates");
      cancelRecording();
      earlierMessagesAbortRef.current?.abort();
      conversationLoadAbortRef.current?.abort();
      startTransition(() => {
        setActiveSection("debates");
        setActiveConversationId(null);
        setActiveConversation(null);
        selectDebateSession(sessionId);
        clearActiveBattleSession();
        setError(null);
        setCollapsedMessageIds(new Set());

        if (!isDesktop) {
          closeMobileSidebar();
        }
      });
    },
    [
      cancelRecording,
      clearActiveBattleSession,
      closeMobileSidebar,
      conversationLoadAbortRef,
      earlierMessagesAbortRef,
      isDesktop,
      onSectionRouteChange,
      selectDebateSession,
      setActiveConversation,
      setActiveConversationId,
      setActiveSection,
      setCollapsedMessageIds,
      setError,
    ],
  );

  const handleSelectBattle = useCallback(
    (sessionId: number) => {
      onSectionRouteChange?.("battle");
      cancelRecording();
      conversationLoadAbortRef.current?.abort();
      earlierMessagesAbortRef.current?.abort();
      clearAttachments();
      startTransition(() => {
        setActiveSection("battle");
        setActiveConversationId(null);
        setActiveConversation(null);
        clearActiveDebate();
        selectBattleSession(sessionId);
        setCollapsedMessageIds(new Set());
        setError(null);

        if (!isDesktop) {
          closeMobileSidebar();
        }
      });
    },
    [
      cancelRecording,
      clearActiveDebate,
      clearAttachments,
      closeMobileSidebar,
      conversationLoadAbortRef,
      earlierMessagesAbortRef,
      isDesktop,
      onSectionRouteChange,
      selectBattleSession,
      setActiveConversation,
      setActiveConversationId,
      setActiveSection,
      setCollapsedMessageIds,
      setError,
    ],
  );

  const handleCreateDebate = useCallback(
    async (payload: Parameters<typeof createDebate>[0]) => {
      try {
        await createDebate(payload);
        setActiveSection("debates");
        clearActiveBattleSession();
        if (!isDesktop) {
          closeMobileSidebar();
        }
      } catch (createError) {
        setError(createError instanceof Error ? createError.message : "Failed to create debate.");
      }
    },
    [clearActiveBattleSession, closeMobileSidebar, createDebate, isDesktop, setActiveSection, setError],
  );

  const handleSelectSection = useCallback(
    (section: WorkspaceSection) => {
      onSectionRouteChange?.(section);
      startTransition(() => {
        setActiveSection(section);
        if (section === "chats") {
          setActiveConversationId(null);
          setActiveConversation(null);
          clearActiveDebate();
          clearActiveBattleSession();
          setCollapsedMessageIds(new Set());
          setError(null);
          return;
        }
        if (section === "battle") {
          cancelRecording();
          conversationLoadAbortRef.current?.abort();
          earlierMessagesAbortRef.current?.abort();
          clearAttachments();
          setActiveConversationId(null);
          setActiveConversation(null);
          clearActiveDebate();
          startNewBattleSession();
          setCollapsedMessageIds(new Set());
          setError(null);
          return;
        }
        if (section === "debates") {
          setActiveConversationId(null);
          setActiveConversation(null);
          openDebateCreate();
          clearActiveBattleSession();
          setCollapsedMessageIds(new Set());
          setError(null);
        }
      });
      if (!isDesktop) {
        closeMobileSidebar();
      }
    },
    [
      cancelRecording,
      clearActiveBattleSession,
      clearActiveDebate,
      clearAttachments,
      closeMobileSidebar,
      conversationLoadAbortRef,
      earlierMessagesAbortRef,
      isDesktop,
      onSectionRouteChange,
      openDebateCreate,
      setActiveConversation,
      setActiveConversationId,
      setActiveSection,
      setCollapsedMessageIds,
      setError,
      startNewBattleSession,
    ],
  );

  return {
    handleCancelCreateDebate,
    handleCreateDebate,
    handleNewChat,
    handleNewDebate,
    handleSelectBattle,
    handleSelectConversation,
    handleSelectDebate,
    handleSelectSection,
  };
}
