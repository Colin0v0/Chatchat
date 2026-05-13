import { useMemo } from "react";

import type { PetCompanionContext } from "../../pet/api/petChat";
import type { ConversationDetail } from "../../../types";
import type { WorkspaceSection } from "./workspaceSections";
import { compactPetContextText, toPetContextMessages } from "./chatAppUtils";

interface UsePetCompanionContextOptions {
  activeConversation: ConversationDetail | null;
  activeSection: WorkspaceSection;
  battleDraft: string;
  draft: string;
  editingUserMessageContent: string;
  selectedModel: string;
}

export function usePetCompanionContext({
  activeConversation,
  activeSection,
  battleDraft,
  draft,
  editingUserMessageContent,
  selectedModel,
}: UsePetCompanionContextOptions): PetCompanionContext {
  return useMemo<PetCompanionContext>(() => {
    const activeDraft = activeSection === "battle"
      ? battleDraft
      : editingUserMessageContent.trim()
        ? editingUserMessageContent
        : draft;

    return {
      activeSection,
      conversation: activeSection === "chats" && activeConversation
        ? {
            id: activeConversation.id,
            messages: toPetContextMessages(activeConversation.messages),
            model: activeConversation.model || selectedModel,
            title: activeConversation.title,
          }
        : null,
      draft: compactPetContextText(activeDraft),
    };
  }, [activeConversation, activeSection, battleDraft, draft, editingUserMessageContent, selectedModel]);
}
