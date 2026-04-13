import type { ConversationSummary, DebateSessionSummary } from "../../types";

export interface SidebarProps {
  items: ConversationSummary[];
  debateItems: DebateSessionSummary[];
  activity?: Record<number, { running: boolean; unread: boolean }>;
  activeConversationId: number | null;
  activeDebateId: number | null;
  conversationsLoaded: boolean;
  debatesLoaded: boolean;
  open: boolean;
  isDesktop: boolean;
  query: string;
  viewerName?: string;
  onQueryChange: (value: string) => void;
  onNewChat: () => void;
  onRename: (conversationId: number, title: string) => void | Promise<void>;
  onDelete: (conversationId: number) => void | Promise<void>;
  onRenameDebate: (sessionId: number, topic: string) => void | Promise<void>;
  onDeleteDebate: (sessionId: number) => void | Promise<void>;
  onLogout?: () => void | Promise<void>;
  onSelect: (conversationId: number) => void;
  onSelectDebate: (sessionId: number) => void;
  onOpenSettings: () => void;
  onToggleSidebar: () => void;
}

export type SidebarSharedProps = Omit<SidebarProps, "isDesktop" | "open" | "onToggleSidebar">;

export type SidebarDialogState =
  | {
      type: "rename";
      kind: "chat" | "debate";
      id: number;
      title: string;
      value: string;
    }
  | {
      type: "delete";
      kind: "chat" | "debate";
      id: number;
      title: string;
    }
  | null;
