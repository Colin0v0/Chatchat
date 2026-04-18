from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from ...debate.common import (
    _advance_after_generated_turn,
    _ensure_free_debate_state,
    _is_free_debate_over,
    _next_stage,
    _next_turn_index,
    _resolve_next_participant,
    load_debate_session_for_user,
)
from ...schemas import DebateJudgeDecisionIn
from ...storage.models import DebateSession, DebateTurn


class DebatePersistenceAdapter:
    def __init__(self, db: Session):
        self.db = db

    def commit_session(self, session: DebateSession, *, refresh_turns: bool = False) -> DebateSession:
        session.updated_at = datetime.utcnow()
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        if refresh_turns:
            self.refresh_session_relations(session)
        return session

    def refresh_session_relations(self, session: DebateSession) -> DebateSession:
        self.db.refresh(session, attribute_names=["turns", "participants"])
        return session

    def resolve_next_participant(self, session: DebateSession):
        from .debate_runtime import DebateStageTransition

        participant, stage_changes = _resolve_next_participant(session)
        self.commit_session(session)
        return participant, DebateStageTransition.from_stage_changes(stage_changes)

    def advance_after_speaker_turn(self, session: DebateSession, completed_stage: str):
        from .debate_runtime import DebateStageTransition

        stage_changes = _advance_after_generated_turn(session, completed_stage)
        self.commit_session(session)
        return DebateStageTransition.from_stage_changes(stage_changes)

    def maybe_advance_free_debate_after_question(self, session: DebateSession):
        from .debate_runtime import DebateStageTransition

        state = _ensure_free_debate_state(session)
        if state is None or not _is_free_debate_over(session, state):
            return DebateStageTransition()
        session.stage = _next_stage(session, "free_debate")
        session.status = "running" if session.stage != "judge_decision" else "waiting_judge"
        self.commit_session(session)
        return DebateStageTransition.from_stage_changes([session.stage])

    def create_judge_question_turn(self, session: DebateSession, question: str) -> DebateTurn:
        question_turn = DebateTurn(
            session=session,
            kind="judge_question",
            stage=session.stage,
            turn_index=_next_turn_index(session),
            prompt_snapshot="",
            content=question.strip(),
        )
        session.updated_at = datetime.utcnow()
        self.db.add(question_turn)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(question_turn)
        return question_turn

    def finalize_debate_decision(
        self,
        session: DebateSession,
        payload: DebateJudgeDecisionIn,
    ) -> DebateSession:
        decision = session.judge_decision
        if decision is None:
            from ...storage.models import DebateJudgeDecision

            decision = DebateJudgeDecision(session=session)

        decision.winner_side = payload.winner_side
        decision.judge_comment = payload.judge_comment.strip()
        decision.scoring_json = json.dumps(payload.scoring_json or {}, ensure_ascii=False)
        self.db.add(decision)
        self.db.flush()

        session.status = "finished"
        session.stage = "judge_decision"
        session.finished_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return load_debate_session_for_user(
            db=self.db,
            session_id=session.id,
            user_id=session.user_id,
        )

    def persist_decision_summary(
        self,
        session: DebateSession,
        summary_chunks: list[str],
    ) -> None:
        session.summary_json = json.dumps({"content": "".join(summary_chunks).strip()}, ensure_ascii=False)
        session.updated_at = datetime.utcnow()
        self.db.add(session)
        self.db.commit()
