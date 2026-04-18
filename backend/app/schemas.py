from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ToolMode = Literal["none", "knowledge", "search"]
ReasoningProfileValue = Literal["off", "auto", "low", "medium", "high", "max", "provider_default"]
FeedbackValue = Literal["up", "down"]
MemoryScope = Literal["working", "global", "conversation"]
MemoryKind = Literal["profile", "preference", "goal", "project", "fact", "constraint"]
MemoryStatus = Literal["candidate", "active", "archived"]
MemoryDocumentType = Literal["user_profile", "workspace_profile", "conversation_brief"]
KnowledgeDocumentStatus = Literal["pending", "indexing", "ready", "failed"]
DebateStatus = Literal["created", "running", "waiting_judge", "finished"]
DebateStage = Literal["opening", "rebuttal", "free_debate", "closing", "judge_decision"]
DebateSide = Literal["pro", "con"]
DebateAskTarget = Literal["all", "pro", "con"]
DecisionWinner = Literal["pro", "con", "draw"]
WordLimitLevel = Literal["short", "standard", "deep"]
DebateEndedReason = Literal["pro_timeout", "con_timeout", "both_timeout", "manual"]


class ConversationSummary(BaseModel):
    id: int
    title: str
    model: str
    updated_at: Optional[datetime] = None
    last_message_preview: str = ""

    model_config = ConfigDict(from_attributes=True)


class ConversationCreate(BaseModel):
    title: str = "New chat"
    model: Optional[str] = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=255)


class UserOut(BaseModel):
    id: int
    username: str

    model_config = ConfigDict(from_attributes=True)


class SessionOut(BaseModel):
    user: UserOut


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class RegenerateRequest(BaseModel):
    conversation_id: int
    assistant_message_id: int
    edited_content: Optional[str] = None
    model: Optional[str] = None
    tool_mode: ToolMode = "none"
    reasoning_profile: Optional[ReasoningProfileValue] = None


class MessageFeedbackUpdate(BaseModel):
    value: Optional[FeedbackValue] = None


class MessageAttachmentOut(BaseModel):
    id: int
    kind: str
    original_name: str
    mime_type: str
    size_bytes: int
    extension: str = ""
    url: str

    model_config = ConfigDict(from_attributes=True)


class MessageSource(BaseModel):
    type: str = "note"
    path: str
    heading: str = ""
    excerpt: str = ""
    score: Optional[float] = None
    title: str = ""
    url: str = ""
    domain: str = ""
    published_at: str = ""
    trust: str = ""
    freshness: str = ""
    match_reason: str = ""


class MessageContextSectionOut(BaseModel):
    kind: str
    title: str
    body: str
    item_count: int = 0


class MessageContextOut(BaseModel):
    query: str = ""
    strategy: str = "balanced"
    tool_mode: ToolMode = "none"
    tool_plan: list[str] = Field(default_factory=list)
    older_message_count: int = 0
    recent_message_count: int = 0
    memory_count: int = 0
    source_count: int = 0
    sections: list[MessageContextSectionOut] = Field(default_factory=list)


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    reasoning: Optional[str] = None
    model: Optional[str] = None
    attachments: list[MessageAttachmentOut] = Field(default_factory=list)
    sources: list[MessageSource] = Field(default_factory=list)
    context: Optional[MessageContextOut] = None
    feedback: Optional[FeedbackValue] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(BaseModel):
    id: int
    title: str
    model: str
    messages: list[MessageOut]
    total_message_count: int = 0
    loaded_message_count: int = 0
    remaining_message_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ConversationMessagePage(BaseModel):
    messages: list[MessageOut]
    loaded_message_count: int = 0
    remaining_message_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class DebateParticipantOut(BaseModel):
    id: int
    model_id: str
    side: DebateSide
    style: str = ""
    order_index: int = 0

    model_config = ConfigDict(from_attributes=True)


class DebateSessionSummaryOut(BaseModel):
    id: int
    topic: str
    status: DebateStatus
    stage: DebateStage
    updated_at: Optional[datetime] = None
    last_turn_preview: str = ""

    model_config = ConfigDict(from_attributes=True)


class DebateSessionCreateIn(BaseModel):
    topic: str = Field(min_length=1, max_length=512)
    pro_model_id: str = Field(min_length=1, max_length=128)
    con_model_id: str = Field(min_length=1, max_length=128)
    judge_model_id: str = ""
    word_limit_level: WordLimitLevel = "standard"
    style: str = ""
    pro_style: str = ""
    con_style: str = ""
    tool_mode: ToolMode = "none"
    free_debate_enabled: bool = True
    opening_duration_sec: int = Field(default=10, ge=5, le=120)
    rebuttal_duration_sec: int = Field(default=10, ge=5, le=120)
    free_debate_duration_sec: int = Field(default=60, ge=10, le=300)
    closing_duration_sec: int = Field(default=15, ge=5, le=180)


class DebateSessionUpdateIn(BaseModel):
    topic: str = Field(min_length=1, max_length=512)


class DebateTurnOut(BaseModel):
    id: int
    kind: str
    stage: DebateStage
    turn_index: int = 0
    speaker_participant_id: Optional[int] = None
    target_turn_id: Optional[int] = None
    content: str = ""
    reasoning: Optional[str] = None
    created_at: Optional[datetime] = None
    elapsed_ms: Optional[int] = None
    truncated: bool = False

    model_config = ConfigDict(from_attributes=True)


class DebateFreeDebateStateOut(BaseModel):
    pro_remaining_ms: int = 0
    con_remaining_ms: int = 0
    active_side: Optional[DebateSide] = None
    active_turn_id: Optional[int] = None
    active_turn_started_at: Optional[str] = None
    turn_count: int = 0
    ended_reason: Optional[DebateEndedReason] = None


class DebateJudgeDecisionOut(BaseModel):
    winner_side: DecisionWinner
    scoring_json: dict[str, object] = Field(default_factory=dict)
    judge_comment: str = ""
    created_at: Optional[datetime] = None


class DebateJudgeAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    ask_to: DebateAskTarget = "all"


class DebateJudgeDecisionIn(BaseModel):
    winner_side: DecisionWinner
    judge_comment: str = ""
    scoring_json: dict[str, object] = Field(default_factory=dict)


class DebateSessionDetailOut(BaseModel):
    id: int
    topic: str
    status: DebateStatus
    stage: DebateStage
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    participants: list[DebateParticipantOut] = Field(default_factory=list)
    turns: list[DebateTurnOut] = Field(default_factory=list)
    judge_decision: Optional[DebateJudgeDecisionOut] = None
    summary: str = ""
    free_debate_enabled: bool = False
    free_debate_state: Optional[DebateFreeDebateStateOut] = None
    stage_time_limits_ms: dict[str, int] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class AudioTranscriptionOut(BaseModel):
    text: str
    language: str
    duration_ms: int


class KnowledgeDocumentOut(BaseModel):
    id: int
    title: str
    mime_type: str
    extension: str
    size_bytes: int
    status: KnowledgeDocumentStatus
    error_message: Optional[str] = None
    chunk_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class KnowledgeStatusOut(BaseModel):
    document_count: int = 0
    pending_document_count: int = 0
    indexing_document_count: int = 0
    ready_document_count: int = 0
    failed_document_count: int = 0
    chunk_count: int = 0
    total_size_bytes: int = 0
    max_documents_per_user: int
    max_total_size_bytes: int
    max_file_size_bytes: int


class KnowledgeReindexResult(BaseModel):
    started: bool = False
    scheduled_documents: int = 0
    indexing_documents: int = 0
    ready_documents: int = 0
    failed_documents: int = 0
    chunk_count: int = 0


class KnowledgeBatchUploadResult(BaseModel):
    created_count: int = 0
    documents: list[KnowledgeDocumentOut] = Field(default_factory=list)


class KnowledgeBatchDeleteIn(BaseModel):
    document_ids: list[int] = Field(min_length=1)


class KnowledgeBatchDeleteResult(BaseModel):
    deleted_count: int = 0
    deleted_ids: list[int] = Field(default_factory=list)


class MemoryItemOut(BaseModel):
    id: int
    scope: MemoryScope
    kind: MemoryKind
    title: str
    detail: str = ""
    tags: list[str] = Field(default_factory=list)
    confidence: float
    status: MemoryStatus
    source_type: str
    modality: str
    write_policy: str
    pinned: bool
    active: bool
    conversation_id: Optional[int] = None
    source_user_message_id: Optional[int] = None
    source_assistant_message_id: Optional[int] = None
    source_attachment_id: Optional[int] = None
    expires_at: Optional[datetime] = None
    last_confirmed_at: Optional[datetime] = None
    promoted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MemoryDocumentOut(BaseModel):
    id: int
    doc_type: MemoryDocumentType
    title: str
    content: str
    source_memory_ids: list[int] = Field(default_factory=list)
    auto_managed: bool
    conversation_id: Optional[int] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MemoryLayerCollectionOut(BaseModel):
    global_items: list[MemoryItemOut] = Field(default_factory=list)
    conversation_items: list[MemoryItemOut] = Field(default_factory=list)
    working_items: list[MemoryItemOut] = Field(default_factory=list)


class MemoryCollectionOut(BaseModel):
    documents: list[MemoryDocumentOut] = Field(default_factory=list)
    active_items: MemoryLayerCollectionOut = Field(default_factory=MemoryLayerCollectionOut)
    candidate_items: MemoryLayerCollectionOut = Field(default_factory=MemoryLayerCollectionOut)


class MemoryCreate(BaseModel):
    scope: Literal["global", "conversation"] = "global"
    kind: MemoryKind = "fact"
    title: str = Field(min_length=1, max_length=255)
    detail: str = ""
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    pinned: bool = False
    active: bool = True
    conversation_id: Optional[int] = None


class MemoryUpdate(BaseModel):
    scope: Literal["global", "conversation"] = "global"
    kind: MemoryKind = "fact"
    title: str = Field(min_length=1, max_length=255)
    detail: str = ""
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    pinned: bool = False
    active: bool = True
    conversation_id: Optional[int] = None


class MemoryPromote(BaseModel):
    scope: Literal["global", "conversation"] = "conversation"
