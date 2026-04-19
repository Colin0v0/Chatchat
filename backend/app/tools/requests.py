from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .plan import ToolContextPlan
from .policy import ToolPolicy

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from ..storage.models import Message


@dataclass(frozen=True)
class ToolPlanRequest:
    query: str
    tool_policy: ToolPolicy


@dataclass(frozen=True)
class ToolContextBuildRequest:
    db: "Session"
    user_id: int
    query: str
    plan: ToolContextPlan
    retrieval_messages: list[dict[str, str]]
    conversation_messages: list["Message"]
    include_file_context: bool
    include_image_context: bool
