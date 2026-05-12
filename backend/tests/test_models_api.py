import json
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.models import _model_love_scores, _model_usage_counts
from app.storage.database import Base
from app.storage.models import (
    BattleSession,
    Conversation,
    DebateJudgeDecision,
    DebateParticipant,
    DebateSession,
    DebateTurn,
    Message,
    Run,
    User,
)


class ModelMetricsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db: Session = self.session_factory()
        self.user = User(username="model-metrics-user", password_hash="hash", is_active=True)
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _add_chat_run(self, *, model_id: str, feedback_value: str | None = None) -> None:
        conversation = Conversation(user_id=self.user.id, title="Chat", model=model_id)
        self.db.add(conversation)
        self.db.flush()

        user_message = Message(conversation_id=conversation.id, role="user", content="hello")
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content="hi",
            feedback_value=feedback_value,
        )
        self.db.add_all([user_message, assistant_message])
        self.db.flush()

        # 中文注释：模型页口碑只看最终 assistant message 的当前赞踩状态。
        self.db.add(
            Run(
                conversation_id=conversation.id,
                user_id=self.user.id,
                request_message_id=user_message.id,
                response_message_id=assistant_message.id,
                mode="chat",
                model_id=model_id,
                provider_family=model_id.split(":", 1)[0],
                reasoning_profile="auto",
                status="completed",
            )
        )

    def test_model_metrics_are_global_love_scores_and_usage_counts(self):
        self._add_chat_run(model_id="openai:gpt-5.4", feedback_value="up")
        self._add_chat_run(model_id="openai:gpt-5.4")
        self._add_chat_run(model_id="anthropic:claude-sonnet", feedback_value="down")
        self._add_chat_run(model_id="google:gemini", feedback_value="down")
        self.db.add(
            BattleSession(
                user_id=self.user.id,
                title="Battle",
                rounds_json=json.dumps(
                    [
                        {
                            "vote": "b",
                            "sides": {
                                "a": {
                                    "status": "done",
                                    "model": {"id": "openai:gpt-5.4", "label": "GPT"},
                                },
                                "b": {
                                    "status": "done",
                                    "model": {
                                        "id": "anthropic:claude-sonnet",
                                        "label": "Claude",
                                    },
                                },
                            },
                        },
                        {
                            "vote": "tie_good",
                            "sides": {
                                "a": {
                                    "status": "running",
                                    "model": {"id": "deepseek:flash", "label": "DeepSeek"},
                                },
                                "b": {
                                    "status": "error",
                                    "model": {"id": "openai:gpt-5.4", "label": "GPT"},
                                },
                            },
                        },
                    ]
                ),
            )
        )
        debate = DebateSession(user_id=self.user.id, topic="Debate", status="finished", stage="judge_decision")
        self.db.add(debate)
        self.db.flush()
        self.db.add_all(
            [
                DebateParticipant(
                    session_id=debate.id,
                    model_id="openai:gpt-5.4",
                    side="pro",
                    style="",
                    order_index=0,
                ),
                DebateParticipant(
                    session_id=debate.id,
                    model_id="anthropic:claude-sonnet",
                    side="con",
                    style="",
                    order_index=1,
                ),
                DebateJudgeDecision(
                    session_id=debate.id,
                    winner_side="con",
                    scoring_json="{}",
                    judge_comment="反方胜。",
                ),
            ]
        )
        self.db.flush()
        con_participant = next(item for item in debate.participants if item.side == "con")
        self.db.add(
            DebateTurn(
                session_id=debate.id,
                kind="speaker_turn",
                stage="opening",
                turn_index=1,
                speaker_participant_id=con_participant.id,
                content="反方发言。",
            )
        )
        self.db.commit()

        self.assertEqual(
            _model_love_scores(self.db),
            {
                "openai:gpt-5.4": 1,
                "anthropic:claude-sonnet": 1,
                "google:gemini": 0,
            },
        )
        self.assertEqual(
            _model_usage_counts(self.db),
            {
                "openai:gpt-5.4": 4,
                "anthropic:claude-sonnet": 3,
                "google:gemini": 1,
            },
        )
