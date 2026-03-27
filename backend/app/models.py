import json
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="New chat")
    model: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text())
    sources_json: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    @property
    def sources(self) -> list[dict[str, str | float]]:
        if not self.sources_json:
            return []

        try:
            payload = json.loads(self.sources_json)
        except json.JSONDecodeError:
            return []

        if not isinstance(payload, list):
            return []

        normalized: list[dict[str, str | float]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).strip()
            heading = str(item.get("heading", "")).strip()
            excerpt = str(item.get("excerpt", "")).strip()
            score_raw = item.get("score")
            if not path:
                continue
            score: float | None = None
            if isinstance(score_raw, (int, float)):
                score = round(float(score_raw), 3)
            normalized.append(
                {
                    "path": path,
                    "heading": heading,
                    "excerpt": excerpt,
                    "score": score,
                }
            )
        return normalized
