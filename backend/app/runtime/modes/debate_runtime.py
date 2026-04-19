from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from fastapi import Request
from sqlalchemy.orm import Session

from ...storage.models import DebateParticipant, DebateSession, DebateTurn
from .debate_persistence import DebatePersistenceAdapter


@dataclass(slots=True)
class DebateRuntimeContext:
    db: Session
    request: Request
    session: DebateSession
    persistence: DebatePersistenceAdapter = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.persistence = DebatePersistenceAdapter(self.db)

    def replace_session(self, session: DebateSession) -> DebateSession:
        self.session = session
        return session


@dataclass(frozen=True, slots=True)
class DebateSpeakerTurnRequest:
    participant: DebateParticipant
    stage: str
    next_turn_index: int
    target_turn_id: int | None = None
    judge_question: str | None = None


@dataclass(frozen=True, slots=True)
class DebateJudgeQuestionContext:
    question_turn: DebateTurn
    question: str
    target_sides: tuple[str, ...]
    previous_status: str


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
