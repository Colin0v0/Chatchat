export type Role = "user" | "assistant" | "system";

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
}

export interface RegenerateChatRequest {
  conversation_id: number;
  assistant_message_id: number;
  model?: string | null;
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
      type: "done";
      assistant_message_id?: number;
    }
  | {
      type: "error";
      message: string;
    };
