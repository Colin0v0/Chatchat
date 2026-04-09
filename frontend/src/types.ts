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

export interface AuthUser {
  id: number;
  username: string;
}

export interface AuthSession {
  user: AuthUser;
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
  total_message_count: number;
  loaded_message_count: number;
  remaining_message_count: number;
}

export interface ConversationMessagePage {
  messages: ChatMessage[];
  loaded_message_count: number;
  remaining_message_count: number;
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

export type KnowledgeDocumentStatus = "pending" | "indexing" | "ready" | "failed";

export interface KnowledgeDocument {
  id: number;
  title: string;
  mime_type: string;
  extension: string;
  size_bytes: number;
  status: KnowledgeDocumentStatus;
  error_message: string | null;
  chunk_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface KnowledgeStatus {
  document_count: number;
  pending_document_count: number;
  indexing_document_count: number;
  ready_document_count: number;
  failed_document_count: number;
  chunk_count: number;
  total_size_bytes: number;
  max_documents_per_user: number;
  max_total_size_bytes: number;
  max_file_size_bytes: number;
}

export interface KnowledgeReindexResult {
  started: boolean;
  scheduled_documents: number;
  indexing_documents: number;
  ready_documents: number;
  failed_documents: number;
  chunk_count: number;
}

export interface KnowledgeBatchUploadResult {
  created_count: number;
  documents: KnowledgeDocument[];
}

export interface KnowledgeBatchDeleteResult {
  deleted_count: number;
  deleted_ids: number[];
}

export type MemoryScope = "working" | "global" | "conversation";
export type MemoryKind = "profile" | "preference" | "goal" | "project" | "fact" | "constraint";
export type MemoryStatus = "candidate" | "active" | "archived";
export type MemoryDocumentType = "user_profile" | "workspace_profile" | "conversation_brief";

export interface MemoryItem {
  id: number;
  scope: MemoryScope;
  kind: MemoryKind;
  title: string;
  detail: string;
  tags: string[];
  confidence: number;
  status: MemoryStatus;
  source_type: string;
  modality: string;
  write_policy: string;
  pinned: boolean;
  active: boolean;
  conversation_id: number | null;
  source_user_message_id: number | null;
  source_assistant_message_id: number | null;
  source_attachment_id: number | null;
  expires_at: string | null;
  last_confirmed_at: string | null;
  promoted_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  last_used_at: string | null;
}

export interface MemoryDocument {
  id: number;
  doc_type: MemoryDocumentType;
  title: string;
  content: string;
  source_memory_ids: number[];
  auto_managed: boolean;
  conversation_id: number | null;
  updated_at: string | null;
}

export interface MemoryLayerCollection {
  global_items: MemoryItem[];
  conversation_items: MemoryItem[];
  working_items: MemoryItem[];
}

export interface MemoryCollection {
  documents: MemoryDocument[];
  active_items: MemoryLayerCollection;
  candidate_items: MemoryLayerCollection;
}

export interface MemoryUpsertPayload {
  scope: Exclude<MemoryScope, "working">;
  kind: MemoryKind;
  title: string;
  detail: string;
  tags: string[];
  confidence: number;
  pinned: boolean;
  active: boolean;
  conversation_id: number | null;
}

export interface MemoryPromotePayload {
  scope: Exclude<MemoryScope, "working">;
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
