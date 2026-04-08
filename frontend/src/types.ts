export type Role = "user" | "assistant" | "system";
export type FeedbackValue = "up" | "down";

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
  type?: "note" | "web" | "file";
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

export interface MessageContextSection {
  kind: "summary" | "history" | "memory" | "retrieval";
  title: string;
  body: string;
  item_count: number;
}

export interface MessageContext {
  query: string;
  strategy: string;
  retrieval_mode: RetrievalMode;
  older_message_count: number;
  recent_message_count: number;
  memory_count: number;
  source_count: number;
  sections: MessageContextSection[];
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
  reasoning?: string;
  attachments?: MessageAttachment[];
  sources?: MessageSource[];
  context?: MessageContext | null;
  feedback?: FeedbackValue | null;
  created_at?: string | null;
  localStatus?: "stopped" | "error";
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
  thinking_enabled?: boolean | null;
}

export interface RegenerateChatRequest {
  conversation_id: number;
  assistant_message_id: number;
  model?: string | null;
  retrieval_mode: RetrievalMode;
  thinking_enabled?: boolean | null;
}

export interface RagReindexResult {
  indexed_files: number;
  indexed_chunks: number;
  failed_chunks: number;
  updated_at: string;
}

export type MemoryScope = "global" | "conversation";
export type MemoryKind = "profile" | "preference" | "goal" | "project" | "fact" | "constraint";

export interface MemoryItem {
  id: number;
  scope: MemoryScope;
  kind: MemoryKind;
  title: string;
  detail: string;
  tags: string[];
  confidence: number;
  pinned: boolean;
  active: boolean;
  conversation_id: number | null;
  source_user_message_id: number | null;
  source_assistant_message_id: number | null;
  created_at: string | null;
  updated_at: string | null;
  last_used_at: string | null;
}

export interface MemoryCollection {
  global_items: MemoryItem[];
  conversation_items: MemoryItem[];
}

export interface MemoryUpsertPayload {
  scope: MemoryScope;
  kind: MemoryKind;
  title: string;
  detail: string;
  tags: string[];
  confidence: number;
  pinned: boolean;
  active: boolean;
  conversation_id: number | null;
}

export interface AudioTranscriptionResult {
  text: string;
  language: string;
  duration_ms: number;
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
      type: "context";
      context: MessageContext;
    }
  | {
      type: "status";
      items: string[];
    }
  | {
      type: "done";
      assistant_message_id?: number;
      conversation_title?: string;
      content?: string;
    }
  | {
      type: "error";
      message: string;
    };
