import unittest
from unittest import mock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.conversations import delete_conversation
from app.storage.database import Base
from app.storage.models import Conversation, Message, Run, RunEvent, User


class ConversationDeleteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db: Session = self.session_factory()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_delete_conversation_removes_run_trace_records(self):
        user = User(username="deleter", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        conversation = Conversation(user_id=user.id, title="Chat", model="openai:gpt-5.4")
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        user_message = Message(conversation_id=conversation.id, role="user", content="hello")
        assistant_message = Message(conversation_id=conversation.id, role="assistant", content="hi")
        self.db.add_all([user_message, assistant_message])
        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(assistant_message)

        run = Run(
            conversation_id=conversation.id,
            user_id=user.id,
            request_message_id=user_message.id,
            response_message_id=assistant_message.id,
            mode="chat",
            model_id="openai:gpt-5.4",
            provider_family="openai",
            reasoning_profile="medium",
            status="completed",
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        self.db.add(
            RunEvent(
                run_id=run.id,
                sequence_no=1,
                event_type="completed",
                payload_json='{"type":"done"}',
            )
        )
        self.db.commit()

        with mock.patch("app.api.conversations.remove_media_files"):
            delete_conversation(conversation_id=conversation.id, db=self.db, current_user=user)

        assert self.db.get(Conversation, conversation.id) is None
        assert self.db.scalar(select(Run).where(Run.id == run.id)) is None
        assert self.db.scalar(select(RunEvent).where(RunEvent.run_id == run.id)) is None
        assert self.db.scalar(select(Message).where(Message.id == user_message.id)) is None
        assert self.db.scalar(select(Message).where(Message.id == assistant_message.id)) is None
