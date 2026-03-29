export type Role = "user" | "assistant" | "system";

export interface MessageAttachment {
  id: number | string;
  kind: "image" | "file";
  original_name: string;
  mime_type: string;
  size_bytes: number;
  extension?: string;
  url: string;
}

export interface MessageSource {
  type?: "note" | "web";
  path: string;
  heading: string;
  excerpt: string;
  score?: number | null;
  title?: string;
  url?: string;
  domain?: string;
  published_at?: string;
  trust?: string;
  freshness?: string;
  match_reason?: string;
}

export interface ConversationSummary {
  id: number;
  title: string;
  model: string;
  updated_at: string | null;
  last_message_preview: string;
}

export interface ChatMessage {
  id: number | string;
  role: Role;
  content: string;
  attachments?: MessageAttachment[];
  sources?: MessageSource[];
  created_at?: string | null;
  localStatus?: "stopped";
}

export interface ConversationDetail {
  id: number;
  title: string;
  model: string;
  messages: ChatMessage[];
}

export interface ModelOption {
  id: string;
  label: string;
  supports_thinking: boolean;
  supports_thinking_trace: boolean;
  supports_image_input: boolean;
  supports_attachment_upload: boolean;
  chat_model: string | null;
  reasoning_model: string | null;
}

export interface ModelsPayload {
  models: ModelOption[];
  default_model: string;
}

export type RetrievalMode = "none" | "rag" | "web";

export interface ChatStreamRequest {
  conversation_id?: number | null;
  message: string;
  files?: File[];
  model?: string | null;
  retrieval_mode: RetrievalMode;
}

export interface RegenerateChatRequest {
  conversation_id: number;
  assistant_message_id: number;
  model?: string | null;
  retrieval_mode: RetrievalMode;
}

export interface RagReindexResult {
  indexed_files: number;
  indexed_chunks: number;
  failed_chunks: number;
  updated_at: string;
}

export type ChatStreamEvent =
  | {
      type: "meta";
      conversation_id: number;
      message_id: number;
      model: string;
    }
  | {
      type: "reasoning";
      content: string;
    }
  | {
      type: "token";
      content: string;
    }
  | {
      type: "sources";
      sources: MessageSource[];
    }
  | {
      type: "status";
      items: string[];
    }
  | {
      type: "done";
      assistant_message_id?: number;
    }
  | {
      type: "error";
      message: string;
    };
