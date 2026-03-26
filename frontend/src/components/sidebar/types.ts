import type { ConversationSummary } from "../../types";

export interface SidebarProps {
  items: ConversationSummary[];
  activeConversationId: number | null;
  conversationsLoaded: boolean;
  open: boolean;
  isDesktop: boolean;
  query: string;
  onQueryChange: (value: string) => void;
  onNewChat: () => void;
  onRename: (conversationId: number, title: string) => void | Promise<void>;
  onDelete: (conversationId: number) => void | Promise<void>;
  onSelect: (conversationId: number) => void;
  onToggleSidebar: () => void;
}

export type SidebarSharedProps = Omit<SidebarProps, "isDesktop" | "open" | "onToggleSidebar">;

export type SidebarDialogState =
  | {
      type: "rename";
      conversationId: number;
      title: string;
      value: string;
    }
  | {
      type: "delete";
      conversationId: number;
      title: string;
    }
  | null;