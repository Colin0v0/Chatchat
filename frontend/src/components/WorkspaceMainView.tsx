import type { ComponentProps } from "react";
import { LoaderCircle } from "lucide-react";

import type { WorkspaceSection } from "../app/workspaceSections";
import { ConversationView } from "./ConversationView";
import { DebateCreateView } from "./DebateCreateView";
import { DebatesHomeView } from "./DebatesHomeView";
import { DebateRoomView } from "./DebateRoomView";
import { KnowledgePage } from "./KnowledgePage";
import { LandingView } from "./LandingView";
import { MemoriesPage } from "./MemoriesPage";
import { ModelsPage } from "./ModelsPage";

type WorkspaceMainViewProps = {
  activeSection: WorkspaceSection;
  conversationProps: ComponentProps<typeof ConversationView> | null;
  debateCreateProps: ComponentProps<typeof DebateCreateView> | null;
  debateRoomProps: ComponentProps<typeof DebateRoomView> | null;
  isConversationLoading: boolean;
  isDebateLoading: boolean;
  knowledgePageProps: ComponentProps<typeof KnowledgePage>;
  landingProps: ComponentProps<typeof LandingView>;
  memoriesPageProps: ComponentProps<typeof MemoriesPage>;
  modelsPageProps: ComponentProps<typeof ModelsPage>;
  onNewDebate: () => void;
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
  conversationProps,
  debateCreateProps,
  debateRoomProps,
  isConversationLoading,
  isDebateLoading,
  knowledgePageProps,
  landingProps,
  memoriesPageProps,
  modelsPageProps,
  onNewDebate,
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

    return <DebatesHomeView onNewDebate={onNewDebate} />;
  }

  if (isConversationLoading) {
    return <LoadingView />;
  }

  if (showLanding || !conversationProps) {
    return <LandingView {...landingProps} />;
  }

  return <ConversationView {...conversationProps} />;
}
