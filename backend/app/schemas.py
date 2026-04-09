from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


RetrievalMode = Literal["none", "rag", "web"]
FeedbackValue = Literal["up", "down"]
MemoryScope = Literal["working", "global", "conversation"]
MemoryKind = Literal["profile", "preference", "goal", "project", "fact", "constraint"]
MemoryStatus = Literal["candidate", "active", "archived"]
MemoryDocumentType = Literal["user_profile", "workspace_profile", "conversation_brief"]
KnowledgeDocumentStatus = Literal["pending", "indexing", "ready", "failed"]


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
    total_message_count: int = 0
    loaded_message_count: int = 0
    remaining_message_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ConversationMessagePage(BaseModel):
    messages: list[MessageOut]
    loaded_message_count: int = 0
    remaining_message_count: int = 0

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
