import type { ComponentProps } from "react";
import { LoaderCircle } from "lucide-react";

import { ConversationView } from "../../chats/ui/ConversationView";
import { LandingView } from "../../chats/ui/LandingView";
import { BattlePage } from "../../battles/ui/BattlePage";
import { DebateCreateView } from "../../debates/ui/DebateCreateView";
import { DebateRoomView } from "../../debates/ui/DebateRoomView";
import { KnowledgePage } from "../../knowledge/ui/KnowledgePage";
import { MemoriesPage } from "../../memories/ui/MemoriesPage";
import { ModelsPage } from "../../models/ui/ModelsPage";
import type { WorkspaceSection } from "../model/workspaceSections";

type WorkspaceMainViewProps = {
  activeSection: WorkspaceSection;
  battlePageProps: ComponentProps<typeof BattlePage>;
  conversationProps: ComponentProps<typeof ConversationView> | null;
  debateCreateProps: ComponentProps<typeof DebateCreateView> | null;
  debateRoomProps: ComponentProps<typeof DebateRoomView> | null;
  isBattleLoading: boolean;
  isConversationLoading: boolean;
  isDebateLoading: boolean;
  knowledgePageProps: ComponentProps<typeof KnowledgePage>;
  landingProps: ComponentProps<typeof LandingView>;
  memoriesPageProps: ComponentProps<typeof MemoriesPage>;
  modelsPageProps: ComponentProps<typeof ModelsPage>;
  showLanding: boolean;
};

function LoadingView() {
  return (
    <section className="flex min-h-0 flex-1 items-center justify-center px-6">
      <div className="flex flex-col items-center gap-4 text-center">
        <LoaderCircle className="size-8 animate-spin text-app-muted" />
      </div>
    </section>
  );
}

export function WorkspaceMainView({
  activeSection,
  battlePageProps,
  conversationProps,
  debateCreateProps,
  debateRoomProps,
  isBattleLoading,
  isConversationLoading,
  isDebateLoading,
  knowledgePageProps,
  landingProps,
  memoriesPageProps,
  modelsPageProps,
  showLanding,
}: WorkspaceMainViewProps) {
  if (activeSection === "models") {
    return <ModelsPage {...modelsPageProps} />;
  }

  if (activeSection === "memories") {
    return <MemoriesPage {...memoriesPageProps} />;
  }

  if (activeSection === "knowledge") {
    return <KnowledgePage {...knowledgePageProps} />;
  }

  if (activeSection === "battle") {
    if (isBattleLoading) {
      return <LoadingView />;
    }
    return <BattlePage {...battlePageProps} />;
  }

  if (activeSection === "debates") {
    if (debateCreateProps) {
      return <DebateCreateView {...debateCreateProps} />;
    }

    if (debateRoomProps) {
      return <DebateRoomView {...debateRoomProps} />;
    }

    if (isDebateLoading) {
      return <LoadingView />;
    }
  }

  if (isConversationLoading) {
    return <LoadingView />;
  }

  if (showLanding || !conversationProps) {
    return <LandingView {...landingProps} />;
  }

  return <ConversationView {...conversationProps} />;
}
