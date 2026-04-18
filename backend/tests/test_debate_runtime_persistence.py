import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.runtime.modes.debate_persistence import DebatePersistenceAdapter
from app.schemas import DebateJudgeDecisionIn


class DebateRuntimePersistenceTests(unittest.TestCase):
    def test_refresh_session_relations_refreshes_turns_and_participants(self):
        db = SimpleNamespace(refresh=Mock())
        adapter = DebatePersistenceAdapter(db)
        session = SimpleNamespace()

        returned = adapter.refresh_session_relations(session)

        self.assertIs(returned, session)
        db.refresh.assert_called_once_with(session, attribute_names=["turns", "participants"])

    def test_resolve_next_participant_wraps_stage_changes_into_transition(self):
        db = SimpleNamespace(add=Mock(), commit=Mock(), refresh=Mock())
        adapter = DebatePersistenceAdapter(db)
        session = SimpleNamespace()
        participant = SimpleNamespace(side="pro")

        with patch(
            "app.runtime.modes.debate_persistence._resolve_next_participant",
            return_value=(participant, ["judge_decision"]),
        ):
            returned_participant, transition = adapter.resolve_next_participant(session)

        self.assertIs(returned_participant, participant)
        self.assertTrue(transition.enters_judge_decision)
        db.add.assert_called_once_with(session)
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(session)

    def test_finalize_debate_decision_updates_existing_decision_and_reloads_session(self):
        db = SimpleNamespace(add=Mock(), flush=Mock(), commit=Mock(), refresh=Mock())
        adapter = DebatePersistenceAdapter(db)
        decision = SimpleNamespace(winner_side=None, judge_comment=None, scoring_json=None)
        session = SimpleNamespace(
            judge_decision=decision,
            status="running",
            stage="free_debate",
            finished_at=None,
            updated_at=None,
            id=9,
            user_id=3,
        )
        reloaded = SimpleNamespace(id=9, user_id=3, status="finished", stage="judge_decision")

        with patch(
            "app.runtime.modes.debate_persistence.load_debate_session_for_user",
            return_value=reloaded,
        ):
            result = adapter.finalize_debate_decision(
                session,
                DebateJudgeDecisionIn(
                    winner_side="con",
                    judge_comment="反方比较完整。",
                    scoring_json={"con_score": 8},
                ),
            )

        self.assertIs(result, reloaded)
        self.assertEqual(decision.winner_side, "con")
        self.assertEqual(decision.judge_comment, "反方比较完整。")
        self.assertEqual(json.loads(decision.scoring_json), {"con_score": 8})
        self.assertEqual(session.status, "finished")
        self.assertEqual(session.stage, "judge_decision")
        self.assertIsNotNone(session.finished_at)
        db.flush.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(session)

    def test_persist_decision_summary_joins_chunks(self):
        db = SimpleNamespace(add=Mock(), commit=Mock())
        adapter = DebatePersistenceAdapter(db)
        session = SimpleNamespace(summary_json=None, updated_at=None)

        adapter.persist_decision_summary(session, ["片段一", "片段二"])

        self.assertEqual(json.loads(session.summary_json), {"content": "片段一片段二"})
        db.add.assert_called_once_with(session)
        db.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
