from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


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


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class RegenerateRequest(BaseModel):
    conversation_id: int
    assistant_message_id: int
    model: Optional[str] = None
    use_rag: bool = False


class MessageSource(BaseModel):
    path: str
    heading: str = ""
    excerpt: str = ""
    score: float | None = None


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    sources: list[MessageSource] = Field(default_factory=list)
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(BaseModel):
    id: int
    title: str
    model: str
    messages: list[MessageOut]

    model_config = ConfigDict(from_attributes=True)


class ChatRequest(BaseModel):
    conversation_id: Optional[int] = None
    message: str = Field(min_length=1)
    model: Optional[str] = None
    use_rag: bool = False


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
