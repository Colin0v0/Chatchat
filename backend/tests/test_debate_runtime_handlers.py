import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.runtime.modes.debate_runtime import DebateRuntimeContext, DebateStageTransition
from app.runtime.modes.debate_stage_handlers import (
    stream_decision_summary_flow,
    stream_stage_followup_events,
)
from app.runtime.modes.debate_turn_handlers import (
    stream_next_turn_rounds,
    stream_question_reply_rounds,
)


async def _drain(generator):
    items = []
    async for item in generator:
        items.append(item)
    return items


class DebateRuntimeStageHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_stage_followup_events_emits_judge_evaluation_on_judge_decision(self):
        db = SimpleNamespace(refresh=Mock())
        request = SimpleNamespace()
        session = SimpleNamespace(stage="judge_decision", turns=[], participants=[])
        context = DebateRuntimeContext(db=db, request=request, session=session)

        async def _fake_judge_eval(*, request, session):
            yield "judge_eval\n"

        with patch("app.runtime.modes.debate_stage_handlers.emit_stage_events", return_value=["stage_changed\n"]), patch(
            "app.runtime.modes.debate_stage_handlers.stream_judge_evaluation_events",
            side_effect=_fake_judge_eval,
        ):
            events = await _drain(
                stream_stage_followup_events(
                    context=context,
                    transition=DebateStageTransition.from_stage_changes(["judge_decision"]),
                )
            )

        self.assertEqual(events, ["stage_changed\n", "judge_eval\n"])
        db.refresh.assert_called_once_with(session, attribute_names=["turns", "participants"])

    async def test_stream_decision_summary_flow_streams_and_persists_summary(self):
        db = SimpleNamespace()
        request = SimpleNamespace()
        session = SimpleNamespace()
        context = DebateRuntimeContext(db=db, request=request, session=session)
        persist_summary = Mock()

        async def _fake_summary_events(*, request, session, judge_note, winner_side, summary_chunks):
            summary_chunks.extend(["片段一", "片段二"])
            yield "summary_token_1\n"
            yield "summary_token_2\n"

        with patch(
            "app.runtime.modes.debate_stage_handlers.decision_summary_context",
            return_value=("pro", "正方比较更完整。"),
        ), patch(
            "app.runtime.modes.debate_stage_handlers.stream_decision_summary_events",
            side_effect=_fake_summary_events,
        ), patch(
            "app.runtime.modes.debate_stage_handlers.persist_decision_summary",
            persist_summary,
        ):
            events = await _drain(
                stream_decision_summary_flow(
                    context=context,
                )
            )

        self.assertEqual(events, ["summary_token_1\n", "summary_token_2\n"])
        persist_summary.assert_called_once_with(
            db=db,
            session=session,
            summary_chunks=["片段一", "片段二"],
        )


class DebateRuntimeTurnHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_next_turn_rounds_stops_after_judge_decision_followup(self):
        participant = SimpleNamespace(side="pro")
        session = SimpleNamespace(stage="free_debate", turns=[], participants=[SimpleNamespace(side="con")])
        context = DebateRuntimeContext(db=SimpleNamespace(), request=SimpleNamespace(), session=session)

        async def _fake_turn_events(**kwargs):
            yield "turn_token\n"

        async def _fake_stage_followups(**kwargs):
            yield "stage_followup\n"

        with patch(
            "app.runtime.modes.debate_turn_handlers.stream_participant_turn_events",
            side_effect=_fake_turn_events,
        ), patch(
            "app.runtime.modes.debate_turn_handlers.advance_after_speaker_turn",
            return_value=DebateStageTransition.from_stage_changes(["judge_decision"]),
        ), patch(
            "app.runtime.modes.debate_turn_handlers.stream_stage_followup_events",
            side_effect=_fake_stage_followups,
        ):
            events = await _drain(
                stream_next_turn_rounds(
                    context=context,
                    participant=participant,
                )
            )

        self.assertEqual(events, ["turn_token\n", "stage_followup\n"])

    async def test_stream_question_reply_rounds_skips_side_without_free_debate_budget(self):
        session = SimpleNamespace(stage="free_debate", turns=[])
        question_turn = SimpleNamespace(id=7)
        context = DebateRuntimeContext(db=SimpleNamespace(), request=SimpleNamespace(), session=session)

        async def _fake_turn_events(*, participant, **kwargs):
            yield f"{participant.side}\n"

        async def _fake_stage_followups(**kwargs):
            if False:
                yield ""

        with patch(
            "app.runtime.modes.debate_turn_handlers.should_stream_question_reply_to_side",
            side_effect=[False, True],
        ), patch(
            "app.runtime.modes.debate_turn_handlers.participant_for_side",
            side_effect=lambda session, side: SimpleNamespace(side=side),
        ), patch(
            "app.runtime.modes.debate_turn_handlers.stream_participant_turn_events",
            side_effect=_fake_turn_events,
        ), patch(
            "app.runtime.modes.debate_turn_handlers.advance_after_speaker_turn",
            return_value=DebateStageTransition(),
        ), patch(
            "app.runtime.modes.debate_turn_handlers.stream_stage_followup_events",
            side_effect=_fake_stage_followups,
        ):
            events = await _drain(
                stream_question_reply_rounds(
                    context=context,
                    target_sides=("pro", "con"),
                    question_turn=question_turn,
                    judge_question="请双方回答",
                )
            )

        self.assertEqual(events, ["con\n"])


if __name__ == "__main__":
    unittest.main()
