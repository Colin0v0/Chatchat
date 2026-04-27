import type {
  AudioSpeechResult,
  AudioTranscriptionResult,
} from "../types";
import { assertApiResponse, toApiUrl } from "../shared/api/http";
export { ApiError, setUnauthorizedHandler, toApiUrl } from "../shared/api/http";
export { fetchSession, login, logout } from "../features/auth/api/session";
export { fetchModels } from "../features/models/api/models";
export {
  deleteKnowledgeDocument,
  deleteKnowledgeDocuments,
  fetchKnowledgeDocuments,
  fetchKnowledgeStatus,
  moveKnowledgeDocuments,
  reindexKnowledgeDocument,
  reindexKnowledgeDocuments,
  uploadKnowledgeDocuments,
} from "../features/knowledge/api/knowledge";
export {
  createMemory,
  deleteMemory,
  dismissMemory,
  fetchMemories,
  promoteMemory,
  updateMemory,
} from "../features/memories/api/memories";
export {
  deleteConversation,
  fetchConversation,
  fetchConversationMessages,
  fetchConversations,
  updateMessageFeedback,
  renameConversation,
} from "../features/chats/api/conversations";
export { regenerateChat, streamChat } from "../features/chats/api/streamChat";
export {
  createDebateSession,
  deleteDebateSession,
  fetchDebateSession,
  fetchDebateSessions,
  renameDebateSession,
  streamDebateAsk,
  streamDebateDecision,
  streamDebateNext,
} from "../features/debates/api/debates";

function audioExtensionForMimeType(mimeType: string): string {
  const normalized = mimeType.toLowerCase();
  if (normalized.startsWith("audio/mp4")) {
    return ".mp4";
  }
  if (
    normalized.startsWith("audio/wav") ||
    normalized.startsWith("audio/wave") ||
    normalized.startsWith("audio/x-wav")
  ) {
    return ".wav";
  }
  return ".webm";
}

function appendAudioFile(formData: FormData, file: Blob) {
  const mimeType = file.type || "audio/webm";
  const namedFile =
    file instanceof File
      ? file
      : new File([file], `recording${audioExtensionForMimeType(mimeType)}`, {
          type: mimeType,
          lastModified: Date.now(),
        });
  formData.append("file", namedFile);
}

export async function transcribeAudio(file: Blob): Promise<AudioTranscriptionResult> {
  const formData = new FormData();
  appendAudioFile(formData, file);

  const response = await fetch(toApiUrl("/api/audio/transcribe"), {
    credentials: "include",
    method: "POST",
    body: formData,
  });
  await assertApiResponse(response);
  return response.json() as Promise<AudioTranscriptionResult>;
}

export async function synthesizeSpeech(payload: {
  text: string;
  voice?: string | null;
  rate?: number | null;
}): Promise<AudioSpeechResult> {
  const response = await fetch(toApiUrl("/api/audio/speech"), {
    credentials: "include",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  await assertApiResponse(response);
  return response.json() as Promise<AudioSpeechResult>;
}
