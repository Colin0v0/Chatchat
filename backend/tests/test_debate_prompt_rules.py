import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.debate.common import _build_summary_messages, _build_turn_messages


def _participant(participant_id: int, side: str, model_id: str):
    return SimpleNamespace(id=participant_id, side=side, model_id=model_id)


def _turn(
    turn_id: int,
    *,
    kind: str,
    stage: str,
    speaker_participant_id: int | None,
    turn_index: int,
    content: str,
    created_at: datetime,
):
    return SimpleNamespace(
        id=turn_id,
        kind=kind,
        stage=stage,
        speaker_participant_id=speaker_participant_id,
        target_turn_id=None,
        turn_index=turn_index,
        content=content,
        reasoning_content="",
        sources_json="{}",
        created_at=created_at,
    )


class DebatePromptRuleTests(unittest.TestCase):
    def test_free_debate_prompt_focuses_on_latest_attack_and_four_piece_rules(self):
        now = datetime.now(timezone.utc)
        pro = _participant(1, "pro", "gpt-pro")
        con = _participant(2, "con", "gpt-con")
        session = SimpleNamespace(
            topic="企业是否应该全面取消 KPI",
            config_json="{}",
            participants=[pro, con],
            turns=[
                _turn(
                    1,
                    kind="speaker_turn",
                    stage="free_debate",
                    speaker_participant_id=2,
                    turn_index=1,
                    content="旧攻击：你们取消 KPI 就等于放弃管理。",
                    created_at=now - timedelta(seconds=20),
                ),
                _turn(
                    2,
                    kind="speaker_turn",
                    stage="free_debate",
                    speaker_participant_id=1,
                    turn_index=2,
                    content="我方刚刚已经说过管理不等于只看一个数字。",
                    created_at=now - timedelta(seconds=15),
                ),
                _turn(
                    3,
                    kind="speaker_turn",
                    stage="free_debate",
                    speaker_participant_id=2,
                    turn_index=3,
                    content="最新攻击：没有 KPI，你怎么证明员工不是在摸鱼？",
                    created_at=now - timedelta(seconds=10),
                ),
            ],
            judge_decision=None,
        )

        messages = _build_turn_messages(session=session, participant=pro, stage="free_debate")

        self.assertEqual(len(messages), 2)
        self.assertIn("只针对对方上一轮最关键的一击或问题", messages[0].content)
        self.assertIn("观点、逻辑、类比/例子/数字、追问", messages[0].content)
        self.assertIn("必须先正面回答，再顺势抛出新的追问", messages[0].content)
        self.assertIn("先直接回答对方或裁判刚刚抛出的攻击/问题", messages[1].content)

        user_prefix = messages[1].content.split("裁判最新追问：")[0]
        self.assertIn("最新攻击：没有 KPI，你怎么证明员工不是在摸鱼？", user_prefix)
        self.assertNotIn("旧攻击：你们取消 KPI 就等于放弃管理。", user_prefix)

    def test_closing_prompt_focuses_on_own_points_and_lift_instead_of_more_fighting(self):
        now = datetime.now(timezone.utc)
        pro = _participant(1, "pro", "gpt-pro")
        con = _participant(2, "con", "gpt-con")
        session = SimpleNamespace(
            topic="企业是否应该全面取消 KPI",
            config_json="{}",
            participants=[pro, con],
            turns=[
                _turn(
                    1,
                    kind="speaker_turn",
                    stage="opening",
                    speaker_participant_id=1,
                    turn_index=1,
                    content="KPI 会把复杂劳动压成单一数字，反而扭曲管理。",
                    created_at=now - timedelta(seconds=30),
                ),
                _turn(
                    2,
                    kind="speaker_turn",
                    stage="opening",
                    speaker_participant_id=2,
                    turn_index=2,
                    content="没有 KPI，管理就失去抓手。",
                    created_at=now - timedelta(seconds=25),
                ),
                _turn(
                    3,
                    kind="speaker_turn",
                    stage="free_debate",
                    speaker_participant_id=2,
                    turn_index=3,
                    content="你们最后还是没证明不用 KPI 怎么判断效率。",
                    created_at=now - timedelta(seconds=10),
                ),
            ],
            judge_decision=None,
        )

        messages = _build_turn_messages(session=session, participant=pro, stage="closing")

        self.assertEqual(len(messages), 2)
        self.assertIn("总结不要再按自由辩节奏逐句缠斗", messages[0].content)
        self.assertIn("归纳我方已经打成的优势", messages[0].content)
        self.assertIn("不要再抛新的追问", messages[1].content)
        self.assertIn("把我方已经打成的 2 到 3 个核心胜点归纳清楚", messages[1].content)
        self.assertNotIn("每一段都尽量做到：有观点、有逻辑、有类比/例子/数字、有追问。", messages[1].content)

    def test_summary_prompt_requires_grounded_lift(self):
        decision = SimpleNamespace(judge_comment="正方把比较标准讲得更清楚。", winner_side="pro")
        session = SimpleNamespace(
            topic="企业是否应该全面取消 KPI",
            turns=[],
            participants=[],
            judge_decision=decision,
        )

        messages = _build_summary_messages(session)

        self.assertEqual(len(messages), 2)
        self.assertIn("观点、逻辑、类比/例子/数字", messages[0].content)
        self.assertIn("情怀和升维", messages[0].content)
        self.assertIn("像赛场结辩收口", messages[0].content)
        self.assertIn("这场辩论说明了什么", messages[0].content)
        self.assertNotIn("对方最大漏洞", messages[0].content)


if __name__ == "__main__":
    unittest.main()
