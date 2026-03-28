export type Role = "user" | "assistant" | "system";

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
  sources?: MessageSource[];
  created_at?: string | null;
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
  chat_model: string | null;
  reasoning_model: string | null;
}

export interface ModelsPayload {
  models: ModelOption[];
  default_model: string;
}

export interface ChatStreamRequest {
  conversation_id?: number | null;
  message: string;
  model?: string | null;
  use_rag?: boolean;
  use_web?: boolean;
}

export interface RegenerateChatRequest {
  conversation_id: number;
  assistant_message_id: number;
  model?: string | null;
  use_rag?: boolean;
  use_web?: boolean;
}

export interface RagReindexResult {
  indexed_files: number;
  indexed_chunks: number;
  failed_chunks: number;
  updated_at: string;
}

export interface ToolPlan {
  tool: "none" | "rag_search" | "web_search" | "both";
  reason: string;
  run_rag: boolean;
  run_web: boolean;
  rag_query: string;
  web_query: string;
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
  | ({
      type: "tool_plan";
    } & ToolPlan)
  | {
      type: "done";
      assistant_message_id?: number;
    }
  | {
      type: "error";
      message: string;
    };
