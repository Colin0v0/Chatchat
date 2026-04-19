import json
import unittest
from types import SimpleNamespace

from app.runtime.modes.debate_policies import (
    debate_session_finished,
    decision_summary_context,
    resolve_question_target_sides,
    should_continue_free_debate_turn_loop,
    should_restore_pre_question_status,
    should_stream_question_reply_to_side,
)


class DebateRuntimePolicyTests(unittest.TestCase):
    def test_debate_session_finished_detects_terminal_status(self):
        self.assertTrue(debate_session_finished(SimpleNamespace(status="finished")))
        self.assertFalse(debate_session_finished(SimpleNamespace(status="running")))

    def test_resolve_question_target_sides_expands_all(self):
        self.assertEqual(resolve_question_target_sides("all"), ("pro", "con"))
        self.assertEqual(resolve_question_target_sides("pro"), ("pro",))

    def test_should_stream_question_reply_to_side_respects_free_debate_budget(self):
        session = SimpleNamespace(
            stage="free_debate",
            config_json=json.dumps(
                {
                    "free_debate_state": {
                        "pro_remaining_ms": 0,
                        "con_remaining_ms": 3000,
                        "active_side": None,
                        "active_turn_id": None,
                        "active_turn_started_at": None,
                        "turn_count": 0,
                        "ended_reason": None,
                    }
                },
                ensure_ascii=False,
            ),
            turns=[],
            participants=[],
        )

        self.assertFalse(should_stream_question_reply_to_side(session=session, side="pro"))
        self.assertTrue(should_stream_question_reply_to_side(session=session, side="con"))

    def test_should_continue_free_debate_turn_loop_only_in_active_free_debate(self):
        self.assertTrue(
            should_continue_free_debate_turn_loop(
                active_stage="free_debate",
                session=SimpleNamespace(stage="free_debate"),
            )
        )
        self.assertFalse(
            should_continue_free_debate_turn_loop(
                active_stage="opening",
                session=SimpleNamespace(stage="free_debate"),
            )
        )
        self.assertFalse(
            should_continue_free_debate_turn_loop(
                active_stage="free_debate",
                session=SimpleNamespace(stage="closing"),
            )
        )

    def test_should_restore_pre_question_status_requires_same_stage(self):
        self.assertTrue(
            should_restore_pre_question_status(
                session=SimpleNamespace(stage="opening"),
                question_stage="opening",
            )
        )
        self.assertFalse(
            should_restore_pre_question_status(
                session=SimpleNamespace(stage="judge_decision"),
                question_stage="free_debate",
            )
        )

    def test_decision_summary_context_reads_saved_judge_decision(self):
        session = SimpleNamespace(
            judge_decision=SimpleNamespace(
                winner_side="con",
                judge_comment="反方比较更完整。",
            )
        )
        self.assertEqual(decision_summary_context(session), ("con", "反方比较更完整。"))
        self.assertEqual(decision_summary_context(SimpleNamespace(judge_decision=None)), ("draw", ""))


if __name__ == "__main__":
    unittest.main()
