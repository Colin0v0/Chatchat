from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from fastapi import Request
from sqlalchemy.orm import Session

from ...storage.models import DebateSession


@dataclass(slots=True)
class DebateRuntimeContext:
    db: Session
    request: Request
    session: DebateSession


@dataclass(frozen=True, slots=True)
class DebateStageTransition:
    stage_changes: tuple[str, ...] = ()
    refresh_relations: bool = False

    @classmethod
    def from_stage_changes(cls, stage_changes: Iterable[str]) -> "DebateStageTransition":
        changes = tuple(stage_changes)
        return cls(
            stage_changes=changes,
            refresh_relations="judge_decision" in changes,
        )

    def __bool__(self) -> bool:
        return bool(self.stage_changes)

    @property
    def enters_judge_decision(self) -> bool:
        return "judge_decision" in self.stage_changes
