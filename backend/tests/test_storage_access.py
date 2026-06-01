import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.storage.access import list_conversation_messages_window, list_user_conversation_summaries
from app.storage.database import Base
from app.storage.models import Conversation, Message, MessageAttachment, Project, Run, User


class ConversationSummaryAccessTests(unittest.TestCase):
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

    def test_list_user_conversation_summaries_prefers_last_message_preview(self):
        user = User(username="tester", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        conversation = Conversation(user_id=user.id, title="Chat", model="openai:test")
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        first = Message(conversation_id=conversation.id, role="user", content="hello")
        second = Message(conversation_id=conversation.id, role="assistant", content="final answer")
        self.db.add_all([first, second])
        self.db.commit()

        summaries = list_user_conversation_summaries(self.db, user_id=user.id)

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].last_message_preview, "final answer")

    def test_list_user_conversation_summaries_falls_back_to_attachment_marker(self):
        user = User(username="tester2", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        conversation = Conversation(user_id=user.id, title="Files", model="openai:test")
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        message = Message(conversation_id=conversation.id, role="user", content="")
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        attachment = MessageAttachment(
            message_id=message.id,
            kind="file",
            original_name="demo.txt",
            mime_type="text/plain",
            relative_path="demo.txt",
            size_bytes=1,
            extension=".txt",
            position=0,
        )
        self.db.add(attachment)
        self.db.commit()

        summaries = list_user_conversation_summaries(self.db, user_id=user.id)

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].last_message_preview, "[Attachment]")

    def test_list_user_conversation_summaries_filters_by_project(self):
        user = User(username="project_filter_tester", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        project_a = Project(user_id=user.id, name="Alpha")
        project_b = Project(user_id=user.id, name="Beta")
        self.db.add_all([project_a, project_b])
        self.db.commit()
        self.db.refresh(project_a)
        self.db.refresh(project_b)

        conversation_a = Conversation(user_id=user.id, project_id=project_a.id, title="Alpha chat", model="openai:test")
        conversation_b = Conversation(user_id=user.id, project_id=project_b.id, title="Beta chat", model="openai:test")
        self.db.add_all([conversation_a, conversation_b])
        self.db.commit()

        summaries = list_user_conversation_summaries(self.db, user_id=user.id, project_id=project_a.id)

        self.assertEqual([summary.title for summary in summaries], ["Alpha chat"])
        self.assertEqual(summaries[0].project_id, project_a.id)

    def test_list_conversation_messages_window_returns_recent_messages(self):
        user = User(username="window_tester", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        conversation = Conversation(user_id=user.id, title="Window", model="openai:test")
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        messages = [
            Message(conversation_id=conversation.id, role="user", content=f"message-{index}")
            for index in range(5)
        ]
        self.db.add_all(messages)
        self.db.commit()

        window = list_conversation_messages_window(
            self.db,
            conversation_id=conversation.id,
            limit=2,
        )

        self.assertEqual([message.content for message in window.messages], ["message-3", "message-4"])
        self.assertEqual(window.loaded_message_count, 2)
        self.assertEqual(window.remaining_message_count, 3)
        self.assertEqual(window.total_message_count, 5)

    def test_list_conversation_messages_window_can_page_older_messages(self):
        user = User(username="page_tester", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        conversation = Conversation(user_id=user.id, title="Older", model="openai:test")
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        messages = [
            Message(conversation_id=conversation.id, role="assistant", content=f"reply-{index}")
            for index in range(6)
        ]
        self.db.add_all(messages)
        self.db.commit()
        first_page = list_conversation_messages_window(
            self.db,
            conversation_id=conversation.id,
            limit=3,
        )

        second_page = list_conversation_messages_window(
            self.db,
            conversation_id=conversation.id,
            limit=2,
            before_message_id=first_page.messages[0].id,
        )

        self.assertEqual([message.content for message in second_page.messages], ["reply-1", "reply-2"])
        self.assertEqual(second_page.loaded_message_count, 2)
        self.assertEqual(second_page.remaining_message_count, 1)
        self.assertEqual(second_page.total_message_count, 6)

    def test_list_conversation_messages_window_hydrates_assistant_model_from_runs(self):
        user = User(username="model_tester", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        conversation = Conversation(user_id=user.id, title="Models", model="codex:gpt-5.4")
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        user_message = Message(conversation_id=conversation.id, role="user", content="hello")
        assistant_message = Message(conversation_id=conversation.id, role="assistant", content="hi")
        self.db.add_all([user_message, assistant_message])
        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(assistant_message)

        self.db.add(
            Run(
                conversation_id=conversation.id,
                user_id=user.id,
                request_message_id=user_message.id,
                response_message_id=assistant_message.id,
                mode="chat",
                model_id="gemini:gemini-3.1-pro-high",
                provider_family="gemini",
                reasoning_profile="medium",
                status="completed",
            )
        )
        self.db.commit()

        window = list_conversation_messages_window(
            self.db,
            conversation_id=conversation.id,
            limit=10,
        )

        self.assertEqual(window.messages[0].model, None)
        self.assertEqual(window.messages[1].model, "gemini:gemini-3.1-pro-high")


if __name__ == "__main__":
    unittest.main()
