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


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
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
