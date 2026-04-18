import { BookOpen, Boxes, Brain, MessageSquare, Scale, Search, type LucideIcon } from "lucide-react";

import { WORKSPACE_SECTION_LABELS } from "../../app/workspaceSections";
import type { WorkspaceSection } from "./types";

export type SidebarPrimaryItem =
  | {
      icon: LucideIcon;
      id: WorkspaceSection;
      kind: "section";
      label: string;
      section: WorkspaceSection;
    }
  | {
      action: "search";
      icon: LucideIcon;
      id: "search";
      kind: "action";
      label: string;
    };

export const SIDEBAR_PRIMARY_ITEMS: SidebarPrimaryItem[] = [
  { icon: MessageSquare, id: "chats", kind: "section", label: WORKSPACE_SECTION_LABELS.chats, section: "chats" },
  { icon: Scale, id: "debates", kind: "section", label: WORKSPACE_SECTION_LABELS.debates, section: "debates" },
  { action: "search", icon: Search, id: "search", kind: "action", label: "Search" },
  { icon: Boxes, id: "models", kind: "section", label: WORKSPACE_SECTION_LABELS.models, section: "models" },
  { icon: Brain, id: "memories", kind: "section", label: WORKSPACE_SECTION_LABELS.memories, section: "memories" },
  { icon: BookOpen, id: "knowledge", kind: "section", label: WORKSPACE_SECTION_LABELS.knowledge, section: "knowledge" },
];
