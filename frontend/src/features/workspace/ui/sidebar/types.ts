import type { WorkspaceSection } from "../../model/workspaceSections";
import type { BattleSessionSummary, ConversationSummary, DebateSessionSummary, ProjectSummary } from "../../../../types";

export type { WorkspaceSection } from "../../model/workspaceSections";

export interface SidebarProps {
  items: ConversationSummary[];
  debateItems: DebateSessionSummary[];
  battleItems: BattleSessionSummary[];
  activity?: Record<number, { running: boolean; unread: boolean }>;
  debateActivity?: Record<number, { running: boolean; unread: boolean }>;
  activeSection: WorkspaceSection;
  activeConversationId: number | null;
  activeDebateId: number | null;
  activeBattleId: number | null;
  activeProjectId: number | null;
  battlesLoaded: boolean;
  conversationsLoaded: boolean;
  debatesLoaded: boolean;
  projects: ProjectSummary[];
  projectsLoaded: boolean;
  projectIsSaving: boolean;
  open: boolean;
  isDesktop: boolean;
  query: string;
  settingsActive?: boolean;
  viewerName?: string;
  onOpenSearch: () => void;
  onQueryChange: (value: string) => void;
  onSelectSection: (section: WorkspaceSection) => void;
  onNewChat: () => void;
  onNewDebate: () => void;
  onCreateProject: (name: string) => Promise<boolean> | boolean;
  onRename: (conversationId: number, title: string) => void | Promise<void>;
  onDelete: (conversationId: number) => void | Promise<void>;
  onRenameDebate: (sessionId: number, topic: string) => void | Promise<void>;
  onDeleteDebate: (sessionId: number) => void | Promise<void>;
  onRenameBattle: (sessionId: number, title: string) => void | Promise<void>;
  onDeleteBattle: (sessionId: number) => void | Promise<void>;
  onLogout?: () => void | Promise<void>;
  onOpenSettings?: () => void;
  onSelect: (conversationId: number) => void;
  onSelectDebate: (sessionId: number) => void;
  onSelectBattle: (sessionId: number) => void;
  onSelectProject: (projectId: number | null) => void;
  onToggleSidebar: () => void;
}

export type SidebarSharedProps = Omit<SidebarProps, "isDesktop" | "open" | "onToggleSidebar">;

export type SidebarDialogState =
  | {
      type: "rename";
      kind: "chat" | "debate" | "battle";
      id: number;
      title: string;
      value: string;
    }
  | {
      type: "delete";
      kind: "chat" | "debate" | "battle";
      id: number;
      title: string;
    }
  | null;
