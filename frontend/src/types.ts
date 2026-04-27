export type Role = "user" | "assistant" | "system";
export type ComposerMode = "chat" | "image";
export type FeedbackValue = "up" | "down";
export type ToolMode = "none" | "knowledge" | "search";
export type ReasoningProfileValue = "off" | "auto" | "low" | "medium" | "high" | "max" | "provider_default";
export type ReasoningControl = "none" | "toggle" | "effort" | "budget" | "prompt_tag";
export type ReasoningVisibility = "none" | "summary" | "full";
export type ReasoningContinuation = "none" | "stateful" | "signature";
export type NativeMultimodalMode = "false" | "codex" | "gemini" | "claude";

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
  tool_mode: ToolMode;
  tool_plan: string[];
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

export interface ChatActiveRun {
  action: "run";
  started_at: string | null;
  run_id?: string | null;
  last_seq?: number | null;
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
  clientKey?: string;
  role: Role;
  content: string;
  reasoning?: string;
  model?: string | null;
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
  active_run?: ChatActiveRun | null;
}

export interface ConversationMessagePage {
  messages: ChatMessage[];
  loaded_message_count: number;
  remaining_message_count: number;
}

export type DebateSide = "pro" | "con";
export type DebateStatus = "created" | "running" | "waiting_judge" | "finished";
export type DebateStage = "opening" | "rebuttal" | "free_debate" | "closing" | "judge_decision";
export type DebateAskTarget = "all" | "pro" | "con";
export type DebateWinner = "pro" | "con" | "draw";
export type WordLimitLevel = "short" | "standard" | "deep";
export type DebateStageScoreKey = "opening" | "rebuttal" | "free_debate" | "closing";
export type DebateEndedReason =
  | "pro_timeout"
  | "con_timeout"
  | "both_timeout"
  | "manual"
  | null;

export interface DebateFreeDebateState {
  pro_remaining_ms: number;
  con_remaining_ms: number;
  active_side: DebateSide | null;
  active_turn_id: number | null;
  active_turn_started_at: string | null;
  turn_count: number;
  ended_reason: DebateEndedReason;
}

export interface DebateParticipant {
  id: number;
  model_id: string;
  side: DebateSide;
  style: string;
  order_index: number;
}

export interface DebateSessionSummary {
  id: number;
  topic: string;
  status: DebateStatus;
  stage: DebateStage;
  updated_at: string | null;
  last_turn_preview: string;
}

export interface DebateActiveRun {
  action: "next" | "ask" | "decision";
  started_at: string | null;
  run_id?: string | null;
  last_seq?: number | null;
}

export interface DebateSessionDetail {
  id: number;
  topic: string;
  status: DebateStatus;
  stage: DebateStage;
  created_at: string | null;
  updated_at: string | null;
  finished_at: string | null;
  participants: DebateParticipant[];
  turns: DebateTurn[];
  judge_decision: DebateJudgeDecision | null;
  ai_suggestion?: DebateAiSuggestion | null;
  summary: string;
  free_debate_enabled: boolean;
  free_debate_state: DebateFreeDebateState | null;
  stage_time_limits_ms: Record<string, number>;
  active_run: DebateActiveRun | null;
}

export interface DebateTurn {
  id: number | string;
  kind: "speaker_turn" | "judge_question" | "system_note";
  stage: DebateStage;
  turn_index: number;
  speaker_participant_id: number | null;
  target_turn_id: number | null;
  content: string;
  reasoning?: string | null;
  created_at: string | null;
  elapsed_ms?: number | null;
  truncated?: boolean;
}

export interface DebateJudgeDecision {
  winner_side: DebateWinner;
  scoring_json: Record<string, unknown>;
  judge_comment: string;
  created_at: string | null;
}

export interface DebateJudgeAnalysis {
  pro_review: string;
  con_review: string;
  shared_feedback: string;
  key_decision: string;
  final_vote: string;
}

export interface DebateAiSuggestion {
  winner: "pro" | "con" | "draw";
  pro_score: number | null;
  con_score: number | null;
  judge_comment: string;
  scoring_json?: Record<string, unknown>;
}

export interface ModelOption {
  id: string;
  label: string;
  supports_thinking: boolean;
  supports_thinking_trace: boolean;
  supports_attachment_upload: boolean;
  provider_name?: string;
  provider_family?: string;
  native_multimodal_mode?: NativeMultimodalMode;
  reasoning_control?: ReasoningControl;
  default_reasoning_profile?: ReasoningProfileValue;
  capabilities?: {
    input: {
      text: boolean;
      image: boolean;
      pdf: boolean;
      other_file: boolean;
      audio: boolean;
    };
    transport: {
      inline_data: boolean;
      file_upload: boolean;
      remote_url: boolean;
    };
    reasoning: {
      control: ReasoningControl;
      supported_profiles: ReasoningProfileValue[];
      visibility: ReasoningVisibility;
      continuation: ReasoningContinuation;
      visible_trace: boolean;
      summary_only: boolean;
    };
    tools: {
      function_calling: boolean;
      parallel_calls: boolean;
      forced_call: boolean;
    };
    stream: {
      text: boolean;
      reasoning: boolean;
      tool_call: boolean;
      usage: boolean;
    };
    state: {
      previous_response: boolean;
    };
  };
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
  files?: File[];
  model?: string | null;
  tool_mode: ToolMode;
  knowledge_folders?: string[];
  reasoning_profile?: ReasoningProfileValue | null;
}

export interface ImageGenerationRequest {
  conversation_id?: number | null;
  prompt: string;
  size?: string | null;
}

export interface DebateSessionCreateRequest {
  topic: string;
  pro_model_id: string;
  con_model_id: string;
  judge_model_id?: string;
  style?: string;
  pro_style?: string;
  con_style?: string;
  tool_mode?: ToolMode;
  free_debate_enabled?: boolean;
  opening_duration_sec?: number;
  rebuttal_duration_sec?: number;
  free_debate_duration_sec?: number;
  closing_duration_sec?: number;
}

export interface DebateAskRequest {
  question: string;
  ask_to: DebateAskTarget;
}

export interface DebateDecisionRequest {
  winner_side: DebateWinner;
  judge_comment?: string;
  scoring_json?: Record<string, unknown>;
}

export interface RegenerateChatRequest {
  conversation_id: number;
  assistant_message_id: number;
  edited_content?: string | null;
  model?: string | null;
  tool_mode: ToolMode;
  knowledge_folders?: string[];
  reasoning_profile?: ReasoningProfileValue | null;
}

export type KnowledgeDocumentStatus = "pending" | "indexing" | "ready" | "failed";

export interface KnowledgeDocument {
  id: number;
  title: string;
  folder: string;
  path: string;
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

export interface KnowledgeBatchMoveResult {
  moved_count: number;
  documents: KnowledgeDocument[];
}

export interface KnowledgeFolderDeleteResult {
  folder: string;
  moved_document_count: number;
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
  reason?: string | null;
}

export interface AudioSpeechResult {
  url: string;
  content_type: string;
  model: string;
  voice: string;
  audio_id?: string | null;
  expires_at?: number | null;
  request_id?: string | null;
  characters?: number | null;
}

type StreamResumeMetadata = {
  run_id?: string;
  seq?: number;
};

type ChatStreamEventPayload =
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

export type ChatStreamEvent = ChatStreamEventPayload & StreamResumeMetadata;

type DebateStreamEventPayload =
  | {
      type: "stage_changed";
      stage: DebateStage;
      status: DebateStatus;
    }
  | {
      type: "judge_question";
      turn: DebateTurn;
    }
  | {
      type: "meta";
      turn: DebateTurn;
    }
  | {
      type: "token";
      turn_id: number;
      content: string;
    }
  | {
      type: "reasoning";
      turn_id: number;
      content: string;
    }
  | {
      type: "turn_done";
      turn: DebateTurn;
    }
  | {
      type: "decision_saved";
      judge_decision: DebateJudgeDecision;
      status: DebateStatus;
      stage: DebateStage;
    }
  | {
      type: "summary_token";
      content: string;
    }
  | {
      type: "judge_analysis_token";
      content: string;
    }
  | {
      type: "free_debate_clock";
      state: DebateFreeDebateState;
    }
  | {
      type: "ai_suggestion";
      suggestion: DebateAiSuggestion;
    }
  | {
      type: "done";
      stage: DebateStage;
      status: DebateStatus;
    }
  | {
      type: "error";
      message: string;
    };

export type DebateStreamEvent = DebateStreamEventPayload & StreamResumeMetadata;
