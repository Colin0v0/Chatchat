import json
import unittest
from unittest.mock import patch

from app.api.battle import BattlePreparedPrompt, _battle_event_stream
from app.chat.types import ChatMessagePayload
from app.runtime.model_runner import ModelStreamChunk
from app.schemas import BattleStreamRequest


async def _collect_payloads(stream):
    payloads = []
    async for line in stream:
        payloads.append(json.loads(line))
    return payloads


class BattleApiStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_battle_stream_emits_model_response_events(self):
        captured: dict[str, object] = {}

        async def fake_stream_model_response(**kwargs):
            captured.update(kwargs)
            yield ModelStreamChunk(reasoning_delta="先想一下")
            yield ModelStreamChunk(output_text_delta="你好")
            yield ModelStreamChunk(output_text_delta="，我是 A")
            yield ModelStreamChunk(done=True)

        with patch(
            "app.api.battle.stream_model_response",
            side_effect=fake_stream_model_response,
        ):
            payloads = await _collect_payloads(
                _battle_event_stream(
                    BattleStreamRequest(
                        message="  你好  ",
                        model="seed-1.8",
                        reasoning_profile="auto",
                    ),
                    BattlePreparedPrompt(messages=[ChatMessagePayload(role="user", content="你好")]),
                )
            )

        # Battle 流只负责匿名对比的一次模型调用，不创建普通聊天会话。
        self.assertEqual(captured["model"], "seed-1.8")
        self.assertEqual(captured["requested_reasoning_profile"], "auto")
        self.assertEqual(captured["messages"][0].content, "你好")
        self.assertEqual(
            payloads,
            [
                {"type": "meta", "model": "seed-1.8"},
                {"type": "reasoning", "content": "先想一下"},
                {"type": "token", "content": "你好"},
                {"type": "token", "content": "，我是 A"},
                {"type": "done", "content": "你好，我是 A"},
            ],
        )

    async def test_battle_stream_emits_error_event(self):
        async def fake_stream_model_response(**kwargs):
            if kwargs:
                raise RuntimeError("上游失败")
            yield ModelStreamChunk(done=True)

        with patch(
            "app.api.battle.stream_model_response",
            side_effect=fake_stream_model_response,
        ):
            payloads = await _collect_payloads(
                _battle_event_stream(
                    BattleStreamRequest(message="你好", model="seed-1.8"),
                    BattlePreparedPrompt(messages=[ChatMessagePayload(role="user", content="你好")]),
                )
            )

        self.assertEqual(payloads[0], {"type": "meta", "model": "seed-1.8"})
        self.assertEqual(payloads[1], {"type": "error", "message": "上游失败"})
