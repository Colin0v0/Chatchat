from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import Request

from ..schemas import DebateJudgeAskIn, DebateJudgeDecisionIn

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ..chat.state import ChatServices
    from ..storage.models import DebateSession
    from ..tools.policy import ToolPolicy


class ModeActionRequest:
    pass


@dataclass(frozen=True)
class ChatRunRequest(ModeActionRequest):
    services: ChatServices
    request: Request
    conversation_id: int
    message_id: int
    model: str
    history_message_ids: list[int]
    query: str
    tool_policy: ToolPolicy
    requested_reasoning: bool | None = None
    requested_reasoning_profile: str | None = None


@dataclass(frozen=True)
class DebateBaseRequest(ModeActionRequest):
    db: Session
    request: Request
    session: DebateSession


@dataclass(frozen=True)
class DebateNextRequest(DebateBaseRequest):
    pass


@dataclass(frozen=True)
class DebateAskRequest(DebateBaseRequest):
    payload: DebateJudgeAskIn


@dataclass(frozen=True)
class DebateDecisionRequest(DebateBaseRequest):
    payload: DebateJudgeDecisionIn
