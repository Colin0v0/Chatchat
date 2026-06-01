import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.media import get_media_file
from app.storage.database import Base
from app.storage.media import remove_media_files, resolve_media_file_path
from app.storage.models import Conversation, Message, MessageAttachment, User


class MediaApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db: Session = self.session_factory()
        self.user = User(username="media-user", password_hash="hash", is_active=True)
        self.other_user = User(username="other-user", password_hash="hash", is_active=True)
        self.db.add_all([self.user, self.other_user])
        self.db.commit()
        self.db.refresh(self.user)
        self.db.refresh(self.other_user)
        self.created_paths: list[str] = []

    def tearDown(self):
        remove_media_files(self.created_paths)
        self.db.close()
        self.engine.dispose()

    def _create_owned_attachment(self) -> str:
        relative_path = f"test/media-api/{uuid4().hex}.txt"
        file_path = resolve_media_file_path(relative_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("owned file", encoding="utf-8")
        self.created_paths.append(relative_path)

        conversation = Conversation(user_id=self.user.id, title="media", model="test:model")
        self.db.add(conversation)
        self.db.flush()
        message = Message(conversation_id=conversation.id, role="user", content="see file")
        self.db.add(message)
        self.db.flush()
        self.db.add(
            MessageAttachment(
                message_id=message.id,
                kind="file",
                original_name="owned.txt",
                mime_type="text/plain",
                relative_path=relative_path,
                size_bytes=10,
                extension=".txt",
            )
        )
        self.db.commit()
        return relative_path

    def test_media_route_serves_owned_attachment(self):
        relative_path = self._create_owned_attachment()

        response = get_media_file(relative_path=relative_path, db=self.db, current_user=self.user)

        self.assertEqual(str(response.path), str(resolve_media_file_path(relative_path)))

    def test_media_route_hides_other_users_attachment(self):
        relative_path = self._create_owned_attachment()

        with self.assertRaises(HTTPException) as error:
            get_media_file(relative_path=relative_path, db=self.db, current_user=self.other_user)

        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
