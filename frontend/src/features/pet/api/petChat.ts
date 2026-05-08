import { apiFetch } from "../../../shared/api/http";

export type PetChatApiMessage = {
  role: "pet" | "user";
  text: string;
};

export type PetChatApiStats = {
  energy: number;
  hunger: number;
  mood: number;
  thirst: number;
};

export type PetChatReplyLength = "normal" | "short" | "tiny";
export type PetChatTone = "bright" | "calm" | "clingy" | "wry";

export type PetCompanionContextMessage = {
  content: string;
  role: "assistant" | "system" | "user";
};

export type PetCompanionContext = {
  activeSection: string;
  conversation: {
    id: number | null;
    messages: PetCompanionContextMessage[];
    model: string;
    title: string;
  } | null;
  draft: string;
};

type PetChatApiRequest = {
  context: PetCompanionContext;
  message: string;
  messages: PetChatApiMessage[];
  replyLength: PetChatReplyLength;
  sleeping: boolean;
  stats: PetChatApiStats;
  tone: PetChatTone;
};

type PetChatApiResponse = {
  reply: string;
};

export async function requestPetChatReply(payload: PetChatApiRequest): Promise<PetChatApiResponse> {
  return apiFetch<PetChatApiResponse>("/api/pet/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
