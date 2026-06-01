import json
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.battle import (
    BattlePreparedPrompt,
    _battle_event_stream,
    create_battle_session,
    delete_battle_session,
    get_battle_preference_dataset,
    get_battle_preference_summary,
    get_battle_session,
    list_battle_sessions,
    rename_battle_session,
    update_battle_session,
)
from app.chat.types import ChatMessagePayload
from app.runtime.model_runner import ModelStreamChunk
from app.schemas import (
    BattleRoundPayload,
    BattleRoundSidesPayload,
    BattleSessionCreateIn,
    BattleSessionRenameIn,
    BattleSessionUpdateIn,
    BattleSideStatePayload,
    BattleStreamRequest,
)
from app.storage.database import Base
from app.storage.models import User


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


class BattleSessionCrudTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db: Session = self.session_factory()
        self.user = User(username="battle-user", password_hash="hash", is_active=True)
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _round_payload(self, *, prompt: str, attachment_url: str | None = None) -> BattleRoundPayload:
        media_url = attachment_url or f"/media/battle/{self.user.id}/files/demo.txt"
        side_a = BattleSideStatePayload(
            id="a",
            model={"id": "openai:gpt-5.4", "label": "GPT"},
            content="回答 A",
            reasoning="推理 A",
            status="done",
            error=None,
            startedAt=1000,
            finishedAt=1200,
        )
        side_b = BattleSideStatePayload(
            id="b",
            model={"id": "claude:sonnet", "label": "Claude"},
            content="回答 B",
            reasoning="推理 B",
            status="done",
            error=None,
            startedAt=1000,
            finishedAt=1250,
        )
        return BattleRoundPayload(
            id="battle-round-1",
            prompt=prompt,
            createdAt="2026-04-30T10:00:00Z",
            revealed=True,
            vote="a",
            sides=BattleRoundSidesPayload(a=side_a, b=side_b),
            attachments=[
                {
                    "id": "battle-attachment-1",
                    "kind": "file",
                    "original_name": "demo.txt",
                    "mime_type": "text/plain",
                    "size_bytes": 12,
                    "extension": ".txt",
                    "url": media_url,
                }
            ],
        )

    def test_battle_session_crud_persists_in_database(self):
        created = create_battle_session(
            payload=BattleSessionCreateIn(
                title="首轮 Battle",
                rounds=[self._round_payload(prompt="先比较这两个模型")],
            ),
            db=self.db,
            current_user=self.user,
        )

        self.assertEqual(created.title, "首轮 Battle")
        self.assertEqual(len(created.rounds), 1)
        self.assertEqual(created.rounds[0].prompt, "先比较这两个模型")

        summaries = list_battle_sessions(db=self.db, current_user=self.user)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].last_message_preview, "先比较这两个模型")

        loaded = get_battle_session(session_id=created.id, db=self.db, current_user=self.user)
        self.assertEqual(loaded.id, created.id)
        self.assertEqual(loaded.rounds[0].sides.a.content, "回答 A")

        updated = update_battle_session(
            session_id=created.id,
            payload=BattleSessionUpdateIn(
                title="第二轮 Battle",
                rounds=[self._round_payload(prompt="继续比较第二题")],
            ),
            db=self.db,
            current_user=self.user,
        )
        self.assertEqual(updated.title, "第二轮 Battle")
        self.assertEqual(updated.rounds[0].prompt, "继续比较第二题")

        renamed = rename_battle_session(
            session_id=created.id,
            payload=BattleSessionRenameIn(title="Battle 已重命名"),
            db=self.db,
            current_user=self.user,
        )
        self.assertEqual(renamed.title, "Battle 已重命名")
        self.assertEqual(renamed.last_message_preview, "继续比较第二题")

    def test_delete_battle_session_removes_media_files(self):
        created = create_battle_session(
            payload=BattleSessionCreateIn(
                title="带附件 Battle",
                rounds=[
                    self._round_payload(
                        prompt="删除时清理附件",
                        attachment_url=f"/media/battle/{self.user.id}/files/2026/demo.txt",
                    )
                ],
            ),
            db=self.db,
            current_user=self.user,
        )

        with patch("app.api.battle.remove_media_files") as remove_media_files:
            delete_battle_session(
                session_id=created.id,
                db=self.db,
                current_user=self.user,
            )

        remove_media_files.assert_called_once_with([f"battle/{self.user.id}/files/2026/demo.txt"])
        self.assertEqual(list_battle_sessions(db=self.db, current_user=self.user), [])

    def test_create_battle_session_rejects_non_battle_media_path(self):
        with self.assertRaises(HTTPException) as error:
            create_battle_session(
                payload=BattleSessionCreateIn(
                    title="非法附件 Battle",
                    rounds=[
                        self._round_payload(
                            prompt="不要接受普通媒体路径",
                            attachment_url="/media/files/2026/demo.txt",
                        )
                    ],
                ),
                db=self.db,
                current_user=self.user,
            )

        self.assertEqual(error.exception.status_code, 400)

    def test_battle_preferences_build_dataset_and_summary(self):
        create_battle_session(
            payload=BattleSessionCreateIn(
                title="偏好沉淀 Battle",
                rounds=[
                    self._round_payload(prompt="第一题"),
                    self._round_payload(prompt="第二题"),
                ],
            ),
            db=self.db,
            current_user=self.user,
        )

        dataset = get_battle_preference_dataset(db=self.db, current_user=self.user)
        summary = get_battle_preference_summary(db=self.db, current_user=self.user)

        self.assertEqual(len(dataset), 2)
        self.assertEqual(dataset[0].prompt, "第一题")
        self.assertEqual(dataset[0].preferred_model_id, "openai:gpt-5.4")
        self.assertEqual(dataset[0].rejected_model_id, "claude:sonnet")
        self.assertEqual(summary.voted_rounds, 2)
        self.assertEqual(summary.a_wins, 2)
        self.assertEqual(summary.b_wins, 0)
        self.assertEqual(summary.model_stats[0].model_id, "openai:gpt-5.4")
        self.assertEqual(summary.model_stats[0].wins, 2)
