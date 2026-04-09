from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


RetrievalMode = Literal["none", "rag", "web"]
FeedbackValue = Literal["up", "down"]
MemoryScope = Literal["global", "conversation"]
MemoryKind = Literal["profile", "preference", "goal", "project", "fact", "constraint"]


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
    model: Optional[str] = None
    retrieval_mode: RetrievalMode = "none"
    thinking_enabled: Optional[bool] = None


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
    retrieval_mode: RetrievalMode = "none"
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

    model_config = ConfigDict(from_attributes=True)


class RagStatus(BaseModel):
    vault_path: str
    index_path: str
    embedding_model: str
    top_k: int
    section_max_chars: int
    candidate_limit: int
    rerank_window: int
    neighbor_window: int
    min_score: float
    chunk_count: int
    updated_at: Optional[str] = None
    vault_exists: bool


class RagReindexResult(BaseModel):
    indexed_files: int
    indexed_chunks: int
    failed_chunks: int = 0
    updated_at: str


class AudioTranscriptionOut(BaseModel):
    text: str
    language: str
    duration_ms: int


class MemoryItemOut(BaseModel):
    id: int
    scope: MemoryScope
    kind: MemoryKind
    title: str
    detail: str = ""
    tags: list[str] = Field(default_factory=list)
    confidence: float
    pinned: bool
    active: bool
    conversation_id: Optional[int] = None
    source_user_message_id: Optional[int] = None
    source_assistant_message_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MemoryCollectionOut(BaseModel):
    global_items: list[MemoryItemOut] = Field(default_factory=list)
    conversation_items: list[MemoryItemOut] = Field(default_factory=list)


class MemoryCreate(BaseModel):
    scope: MemoryScope = "global"
    kind: MemoryKind = "fact"
    title: str = Field(min_length=1, max_length=255)
    detail: str = ""
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    pinned: bool = False
    active: bool = True
    conversation_id: Optional[int] = None


class MemoryUpdate(BaseModel):
    scope: MemoryScope
    kind: MemoryKind
    title: str = Field(min_length=1, max_length=255)
    detail: str = ""
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    pinned: bool = False
    active: bool = True
    conversation_id: Optional[int] = None
