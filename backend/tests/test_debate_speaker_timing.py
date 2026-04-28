import asyncio
import json
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

from app.runtime.model_runner import ModelStreamChunk
from app.runtime.modes.debate_execution import stream_speaker_turn


class FakeDebateTurn:
    def __init__(
        self,
        *,
        session,
        kind,
        stage,
        turn_index,
        speaker_participant_id,
        target_turn_id,
        prompt_snapshot,
        content,
    ):
        self.id = None
        self.session = session
        self.kind = kind
        self.stage = stage
        self.turn_index = turn_index
        self.speaker_participant_id = speaker_participant_id
        self.target_turn_id = target_turn_id
        self.prompt_snapshot = prompt_snapshot
        self.content = content
        self.reasoning_content = None
        self.sources_json = None
        self.created_at = None
        session.turns.append(self)


class FakeDb:
    def __init__(self):
        self.next_id = 100

    def add(self, item):
        return None

    def commit(self):
        return None

    def refresh(self, item, attribute_names=None):
        if hasattr(item, "id") and item.id is None:
            item.id = self.next_id
            self.next_id += 1


class FakeRequest:
    async def is_disconnected(self):
        return False


@asynccontextmanager
async def fake_reserve_model_execution(request, model_id):
    yield


async def collect_payloads(stream):
    payloads = []
    async for line in stream:
        payloads.append(json.loads(line))
    return payloads


class DebateSpeakerTimingTests(unittest.IsolatedAsyncioTestCase):
    async def test_reasoning_before_answer_does_not_consume_turn_budget(self):
        session = SimpleNamespace(
            config_json=json.dumps({"free_debate_enabled": False}, ensure_ascii=False),
            turns=[],
            participants=[],
            updated_at=None,
        )
        participant = SimpleNamespace(id=7, side="pro", model_id="test:model")

        async def fake_stream_model_response(**kwargs):
            yield ModelStreamChunk(reasoning_delta="先思考")
            await asyncio.sleep(0.02)
            yield ModelStreamChunk(output_text_delta="正式发言")
            yield ModelStreamChunk(done=True)

        with patch("app.runtime.modes.debate_execution.DebateTurn", FakeDebateTurn), patch(
            "app.runtime.modes.debate_execution.reserve_model_execution",
            fake_reserve_model_execution,
        ), patch(
            "app.runtime.modes.debate_execution.stream_model_response",
            side_effect=fake_stream_model_response,
        ), patch(
            "app.runtime.modes.debate_execution._build_turn_messages",
            return_value=[SimpleNamespace(content="prompt")],
        ), patch(
            "app.runtime.modes.debate_execution._stage_turn_budget_ms",
            return_value=10,
        ):
            payloads = await collect_payloads(
                stream_speaker_turn(
                    db=FakeDb(),
                    request=FakeRequest(),
                    session=session,
                    participant=participant,
                    stage="opening",
                    next_turn_index=1,
                )
            )

        token_payload = next(payload for payload in payloads if payload["type"] == "token")
        done_payload = next(payload for payload in payloads if payload["type"] == "turn_done")
        self.assertEqual(token_payload["content"], "正式发言")
        self.assertEqual(done_payload["turn"]["content"], "正式发言")
        self.assertFalse(done_payload["turn"]["truncated"])

    async def test_free_debate_clock_starts_when_answer_text_starts(self):
        session = SimpleNamespace(
            config_json=json.dumps(
                {
                    "free_debate_enabled": True,
                    "free_debate_budget_ms": 1000,
                },
                ensure_ascii=False,
            ),
            turns=[],
            participants=[],
            updated_at=None,
        )
        participant = SimpleNamespace(id=8, side="con", model_id="test:model")

        async def fake_stream_model_response(**kwargs):
            yield ModelStreamChunk(reasoning_delta="先思考")
            yield ModelStreamChunk(output_text_delta="正式发言")
            yield ModelStreamChunk(done=True)

        with patch("app.runtime.modes.debate_execution.DebateTurn", FakeDebateTurn), patch(
            "app.runtime.modes.debate_execution.reserve_model_execution",
            fake_reserve_model_execution,
        ), patch(
            "app.runtime.modes.debate_execution.stream_model_response",
            side_effect=fake_stream_model_response,
        ), patch(
            "app.runtime.modes.debate_execution._build_turn_messages",
            return_value=[SimpleNamespace(content="prompt")],
        ):
            payloads = await collect_payloads(
                stream_speaker_turn(
                    db=FakeDb(),
                    request=FakeRequest(),
                    session=session,
                    participant=participant,
                    stage="free_debate",
                    next_turn_index=1,
                )
            )

        clock_payloads = [payload for payload in payloads if payload["type"] == "free_debate_clock"]
        speaker_clock = next(payload for payload in payloads if payload["type"] == "speaker_clock")

        self.assertIsNone(clock_payloads[0]["state"]["active_turn_started_at"])
        self.assertEqual(clock_payloads[1]["state"]["active_turn_started_at"], speaker_clock["started_at"])
        self.assertEqual(clock_payloads[1]["state"]["active_side"], "con")


if __name__ == "__main__":
    unittest.main()
