import json
import unittest
from types import SimpleNamespace

from app.debate.common import _build_ai_evaluation_messages, _normalize_decision_scoring, _parse_ai_evaluation


class DebateJudgeLogicTests(unittest.TestCase):
    def test_build_ai_evaluation_messages_reuses_commentary(self):
        session = SimpleNamespace(topic="是否应鼓励远程办公", turns=[], participants=[])

        messages = _build_ai_evaluation_messages(
            session,
            commentary_markdown="## 最终投票\n\n本场我投正方一票",
        )

        self.assertEqual(len(messages), 2)
        self.assertIn("JSON 裁决必须与该讲评保持一致", messages[0].content)
        self.assertIn("你刚刚已经给出的讲评", messages[1].content)
        self.assertIn("本场我投正方一票", messages[1].content)

    def test_parse_ai_evaluation_normalizes_conflicting_vote_and_scores(self):
        raw = json.dumps(
            {
                "winner": "pro",
                "pro_score": 81,
                "con_score": 87,
                "judge_comment": "我更认可正方的价值判断。",
                "analysis": {
                    "pro_review": "正方框架完整。",
                    "con_review": "反方回应犀利。",
                    "shared_feedback": "双方都有交锋。",
                    "key_decision": "自由辩决定胜负。",
                    "final_vote": "本场我投正方一票",
                },
                "stage_scores": {
                    "opening": {"pro": 20, "con": 21},
                    "rebuttal": {"pro": 19, "con": 22},
                    "free_debate": {"pro": 21, "con": 23},
                    "closing": {"pro": 21, "con": 21},
                },
                "issues": {"pro": [], "con": [], "shared": []},
            },
            ensure_ascii=False,
        )

        parsed = _parse_ai_evaluation(raw)

        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["winner"], "con")
        self.assertEqual(parsed["pro_score"], 81)
        self.assertEqual(parsed["con_score"], 87)
        self.assertEqual(parsed["scoring_json"]["analysis"]["final_vote"], "本场我投反方一票")

    def test_normalize_decision_scoring_prefers_numeric_result(self):
        winner, scoring = _normalize_decision_scoring(
            winner_side="pro",
            scoring_json={
                "pro_score": 76,
                "con_score": 82,
                "analysis": {
                    "pro_review": "正方有亮点。",
                    "con_review": "反方更完整。",
                    "shared_feedback": "",
                    "key_decision": "反方比较更充分。",
                    "final_vote": "本场我投正方一票",
                },
            },
        )

        self.assertEqual(winner, "con")
        self.assertEqual(scoring["analysis"]["final_vote"], "本场我投反方一票")
        self.assertEqual(scoring["pro_score"], 76)
        self.assertEqual(scoring["con_score"], 82)


if __name__ == "__main__":
    unittest.main()
