from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from ..core.config import settings
from .database import Base
from .media import media_url


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")
    battle_sessions: Mapped[list["BattleSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(BattleSession.updated_at)",
    )
    memories: Mapped[list["MemoryItem"]] = relationship(back_populates="user")
    memory_documents: Mapped[list["MemoryDocument"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="MemoryDocument.updated_at",
    )
    memory_settings: Mapped[Optional["UserMemorySettings"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    chat_history_entries: Mapped[list["ChatHistoryEntry"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(ChatHistoryEntry.updated_at)",
    )
    knowledge_documents: Mapped[list["KnowledgeDocument"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="KnowledgeDocument.updated_at",
    )
    knowledge_folders: Mapped[list["KnowledgeFolder"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="KnowledgeFolder.name",
    )
    pet_state: Mapped[Optional["PetState"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(UserSession.created_at)",
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="sessions")


class PetState(Base):
    # 中文注释：桌面小狐狸的跨设备状态，和用户是一对一关系。
    __tablename__ = "pet_states"
    __table_args__ = (UniqueConstraint("user_id", name="uq_pet_states_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sleeping: Mapped[bool] = mapped_column(Boolean, default=False)
    energy: Mapped[int] = mapped_column(Integer, default=78)
    hunger: Mapped[int] = mapped_column(Integer, default=76)
    mood: Mapped[int] = mapped_column(Integer, default=82)
    thirst: Mapped[int] = mapped_column(Integer, default=74)
    position_bottom: Mapped[float] = mapped_column(Float, default=96)
    position_left: Mapped[float] = mapped_column(Float, default=28)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="pet_state")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="New chat")
    model: Mapped[str] = mapped_column(String(128))
    temporary_chat: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[Optional[User]] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    memories: Mapped[list["MemoryItem"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="MemoryItem.updated_at",
    )
    memory_documents: Mapped[list["MemoryDocument"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="MemoryDocument.updated_at",
    )
    chat_history_entries: Mapped[list["ChatHistoryEntry"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="desc(ChatHistoryEntry.updated_at)",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text())
    reasoning_content: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    image_context: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    attachment_context: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    response_mode: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    sources_json: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    context_json: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    feedback_value: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    brainstorm_json: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    attachments: Mapped[list["MessageAttachment"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="MessageAttachment.position, MessageAttachment.id",
    )

    @property
    def sources(self) -> list[dict[str, object]]:
        if not self.sources_json:
            return []

        try:
            payload = json.loads(self.sources_json)
        except json.JSONDecodeError:
            return []

        if not isinstance(payload, list):
            return []

        normalized: list[dict[str, object]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            source_type = str(item.get("type", "note")).strip() or "note"
            path = str(item.get("path", "")).strip()
            heading = str(item.get("heading", "")).strip()
            excerpt = str(item.get("excerpt", "")).strip()
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            domain = str(item.get("domain", "")).strip()
            published_at = str(item.get("published_at", "")).strip()
            trust = str(item.get("trust", "")).strip()
            freshness = str(item.get("freshness", "")).strip()
            match_reason = str(item.get("match_reason", "")).strip()
            score_raw = item.get("score")
            if not path and not url:
                continue
            score: Optional[float] = None
            if isinstance(score_raw, (int, float)):
                score = round(float(score_raw), 3)
            normalized.append(
                {
                    "type": source_type,
                    "path": path,
                    "heading": heading,
                    "excerpt": excerpt,
                    "title": title,
                    "url": url,
                    "domain": domain,
                    "published_at": published_at,
                    "trust": trust,
                    "freshness": freshness,
                    "match_reason": match_reason,
                    "score": score,
                }
            )
        return normalized

    @property
    def brainstorm(self) -> Optional[dict[str, object]]:
        if not self.brainstorm_json:
            return None

        try:
            payload = json.loads(self.brainstorm_json)
        except json.JSONDecodeError:
            return None

        return payload if isinstance(payload, dict) else None

    @property
    def context(self) -> Optional[dict[str, object]]:
        if not self.context_json:
            return None

        try:
            payload = json.loads(self.context_json)
        except json.JSONDecodeError:
            return None

        return payload if isinstance(payload, dict) else None

    @property
    def pending_memories(self) -> list[object]:
        value = getattr(self, "_pending_memories", None)
        return value if isinstance(value, list) else []

    @property
    def responseMode(self) -> str:
        return (self.response_mode or "normal").strip() or "normal"

    @property
    def reasoning(self) -> str | None:
        value = (self.reasoning_content or "").strip()
        return value or None

    @property
    def model(self) -> str | None:
        value = getattr(self, "_resolved_model_id", None)
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    @property
    def feedback(self) -> str | None:
        value = (self.feedback_value or "").strip()
        return value or None


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"))
    kind: Mapped[str] = mapped_column(String(24), default="image")
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(128))
    relative_path: Mapped[str] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(Integer)
    extension: Mapped[str] = mapped_column(String(32), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    message: Mapped[Message] = relationship(back_populates="attachments")
    provider_file_refs: Mapped[list["ProviderFileRef"]] = relationship(
        back_populates="attachment",
        cascade="all, delete-orphan",
        order_by="ProviderFileRef.created_at",
    )

    @property
    def url(self) -> str:
        return media_url(self.relative_path)


class ProviderFileRef(Base):
    __tablename__ = "provider_file_refs"
    __table_args__ = (
        UniqueConstraint(
            "attachment_id",
            "provider_family",
            "base_url_hash",
            name="uq_provider_file_refs_attachment_provider_base",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    attachment_id: Mapped[int] = mapped_column(ForeignKey("message_attachments.id"), index=True)
    provider_family: Mapped[str] = mapped_column(String(48), index=True)
    base_url_hash: Mapped[str] = mapped_column(String(64))
    remote_file_id: Mapped[str] = mapped_column(String(255))
    remote_purpose: Mapped[str] = mapped_column(String(64), default="user_data")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    attachment: Mapped[MessageAttachment] = relationship(back_populates="provider_file_refs")


class ImageGenerationJob(Base):
    __tablename__ = "image_generation_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    user_message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), index=True)
    assistant_message_id: Mapped[Optional[int]] = mapped_column(ForeignKey("messages.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    prompt: Mapped[str] = mapped_column(Text())
    size: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    quality: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    output_format: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    model: Mapped[str] = mapped_column(String(128))
    error_message: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("conversations.id"), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    request_message_id: Mapped[Optional[int]] = mapped_column(ForeignKey("messages.id"), nullable=True, index=True)
    response_message_id: Mapped[Optional[int]] = mapped_column(ForeignKey("messages.id"), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(32), default="chat", index=True)
    model_id: Mapped[str] = mapped_column(String(128), index=True)
    provider_family: Mapped[str] = mapped_column(String(48), index=True)
    reasoning_profile: Mapped[str] = mapped_column(String(32), default="auto")
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["RunEvent"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="RunEvent.sequence_no",
    )

    @property
    def metadata_payload(self) -> dict[str, object]:
        if not self.metadata_json:
            return {}
        try:
            payload = json.loads(self.metadata_json)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence_no", name="uq_run_events_run_id_sequence_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    sequence_no: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[Run] = relationship(back_populates="events")

    @property
    def payload(self) -> dict[str, object]:
        try:
            parsed = json.loads(self.payload_json or "{}")
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}


class MemoryItem(Base):
    __tablename__ = "memory_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(24), default="conversation")
    kind: Mapped[str] = mapped_column(String(32), default="fact")
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(Text(), default="")
    tags_json: Mapped[str] = mapped_column(Text(), default="[]")
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    confidence_state: Mapped[str] = mapped_column(String(24), default="inferred")
    evidence_count: Mapped[int] = mapped_column(Integer, default=1)
    evidence_json: Mapped[str] = mapped_column(Text(), default="[]")
    status: Mapped[str] = mapped_column(String(24), default="active")
    source_type: Mapped[str] = mapped_column(String(24), default="manual")
    modality: Mapped[str] = mapped_column(String(24), default="text")
    write_policy: Mapped[str] = mapped_column(String(24), default="manual")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("conversations.id"),
        nullable=True,
    )
    source_user_message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("messages.id"),
        nullable=True,
    )
    source_assistant_message_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("messages.id"),
        nullable=True,
    )
    source_attachment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("message_attachments.id"),
        nullable=True,
    )
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(settings.knowledge_embedding_dimensions), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    promoted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[Optional[User]] = relationship(back_populates="memories")
    conversation: Mapped[Optional[Conversation]] = relationship(back_populates="memories")

    @property
    def tags(self) -> list[str]:
        try:
            payload = json.loads(self.tags_json or "[]")
        except json.JSONDecodeError:
            return []

        if not isinstance(payload, list):
            return []

        normalized: list[str] = []
        for item in payload:
            value = str(item).strip()
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    @property
    def evidence(self) -> list[dict[str, object]]:
        try:
            payload = json.loads(self.evidence_json or "[]")
        except json.JSONDecodeError:
            return []

        if not isinstance(payload, list):
            return []

        normalized: list[dict[str, object]] = []
        for item in payload:
            if isinstance(item, dict):
                normalized.append(item)
        return normalized


class MemoryDocument(Base):
    __tablename__ = "memory_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("conversations.id"), nullable=True, index=True)
    doc_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text(), default="")
    source_memory_ids_json: Mapped[str] = mapped_column(Text(), default="[]")
    auto_managed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="memory_documents")
    conversation: Mapped[Optional[Conversation]] = relationship(back_populates="memory_documents")

    @property
    def source_memory_ids(self) -> list[int]:
        try:
            payload = json.loads(self.source_memory_ids_json or "[]")
        except json.JSONDecodeError:
            return []

        if not isinstance(payload, list):
            return []

        normalized: list[int] = []
        for item in payload:
            if isinstance(item, int) and item not in normalized:
                normalized.append(item)
        return normalized


class UserMemorySettings(Base):
    __tablename__ = "user_memory_settings"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_memory_settings_user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    saved_memories_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reference_chat_history_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    memory_learning_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sensitive_memory_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="memory_settings")


class ChatHistoryEntry(Base):
    __tablename__ = "chat_history_entries"
    __table_args__ = (
        UniqueConstraint(
            "assistant_message_id",
            name="uq_chat_history_entries_assistant_message_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    user_message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    assistant_message_id: Mapped[int] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"), index=True)
    conversation_title: Mapped[str] = mapped_column(String(255), default="")
    user_text: Mapped[str] = mapped_column(Text(), default="")
    assistant_text: Mapped[str] = mapped_column(Text(), default="")
    summary: Mapped[str] = mapped_column(Text(), default="")
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(settings.knowledge_embedding_dimensions), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="chat_history_entries")
    conversation: Mapped[Conversation] = relationship(back_populates="chat_history_entries")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    folder: Mapped[str] = mapped_column(String(255), default="")
    mime_type: Mapped[str] = mapped_column(String(128))
    extension: Mapped[str] = mapped_column(String(32), default=".md")
    size_bytes: Mapped[int] = mapped_column(Integer)
    relative_path: Mapped[str] = mapped_column(String(512))
    sha1: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="knowledge_documents")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="KnowledgeChunk.chunk_index",
    )

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    @property
    def path(self) -> str:
        normalized_folder = (self.folder or "").strip().strip("/")
        if not normalized_folder:
            return self.title
        return f"{normalized_folder}/{self.title}"


class KnowledgeFolder(Base):
    __tablename__ = "knowledge_folders"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_knowledge_folders_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="knowledge_folders")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    chunk_key: Mapped[str] = mapped_column(String(64), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(String(255))
    directory: Mapped[str] = mapped_column(String(255), default="")
    heading: Mapped[str] = mapped_column(String(255), default="Overview")
    content: Mapped[str] = mapped_column(Text())
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    tags_json: Mapped[str] = mapped_column(Text(), default="[]")
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.knowledge_embedding_dimensions))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")

    @property
    def tags(self) -> list[str]:
        try:
            payload = json.loads(self.tags_json or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, list):
            return []
        normalized: list[str] = []
        for item in payload:
            value = str(item).strip()
            if value and value not in normalized:
                normalized.append(value)
        return normalized


class BattleSession(Base):
    __tablename__ = "battle_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    rounds_json: Mapped[str] = mapped_column(Text(), default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="battle_sessions")

    @property
    def rounds(self) -> list[dict[str, object]]:
        payload = json.loads(self.rounds_json or "[]")
        if not isinstance(payload, list):
            raise ValueError("battle session rounds must be a list")
        return payload


class DebateSession(Base):
    __tablename__ = "debate_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    topic: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(24), default="created", index=True)
    stage: Mapped[str] = mapped_column(String(32), default="opening", index=True)
    config_json: Mapped[str] = mapped_column(Text(), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)

    user: Mapped[User] = relationship()
    participants: Mapped[list["DebateParticipant"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="DebateParticipant.order_index",
    )
    turns: Mapped[list["DebateTurn"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="DebateTurn.created_at",
    )
    judge_decision: Mapped[Optional["DebateJudgeDecision"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        uselist=False,
    )


class DebateParticipant(Base):
    __tablename__ = "debate_participants"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("debate_sessions.id"), index=True)
    model_id: Mapped[str] = mapped_column(String(128))
    side: Mapped[str] = mapped_column(String(16), default="pro", index=True)
    style: Mapped[str] = mapped_column(String(32), default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[DebateSession] = relationship(back_populates="participants")


class DebateTurn(Base):
    __tablename__ = "debate_turns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("debate_sessions.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24), default="speaker_turn", index=True)
    stage: Mapped[str] = mapped_column(String(32), default="opening", index=True)
    turn_index: Mapped[int] = mapped_column(Integer, default=0, index=True)
    speaker_participant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("debate_participants.id"),
        nullable=True,
        index=True,
    )
    target_turn_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("debate_turns.id"),
        nullable=True,
        index=True,
    )
    prompt_snapshot: Mapped[str] = mapped_column(Text(), default="")
    content: Mapped[str] = mapped_column(Text(), default="")
    reasoning_content: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    sources_json: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[DebateSession] = relationship(back_populates="turns")
    speaker: Mapped[Optional[DebateParticipant]] = relationship(foreign_keys=[speaker_participant_id])


class DebateJudgeDecision(Base):
    __tablename__ = "debate_judge_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("debate_sessions.id"), unique=True, index=True)
    winner_side: Mapped[str] = mapped_column(String(16), default="draw")
    scoring_json: Mapped[str] = mapped_column(Text(), default="{}")
    judge_comment: Mapped[str] = mapped_column(Text(), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[DebateSession] = relationship(back_populates="judge_decision")
