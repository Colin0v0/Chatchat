import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.chat.context import save_assistant_message
from app.schemas import MessageOut
from app.storage.database import Base
from app.storage.models import Conversation, Message


class MessagePersistenceTests(unittest.TestCase):
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

    def test_save_assistant_message_persists_reasoning_content(self):
        conversation = Conversation(title="Test", model="openai:test")
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        assistant_message = save_assistant_message(
            db=self.db,
            conversation=conversation,
            content="final answer",
            reasoning="step 1\nstep 2",
            sources=[],
            context_payload=None,
        )

        stored_message = self.db.scalar(select(Message).where(Message.id == assistant_message.id))
        assert stored_message is not None

        self.assertEqual(stored_message.reasoning_content, "step 1\nstep 2")
        self.assertEqual(stored_message.reasoning, "step 1\nstep 2")

        payload = MessageOut.model_validate(stored_message)
        self.assertEqual(payload.reasoning, "step 1\nstep 2")
        self.assertIsNone(payload.model)


if __name__ == "__main__":
    unittest.main()
