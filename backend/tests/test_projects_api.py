import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.projects import create_project, delete_project, list_projects, update_project
from app.schemas import ProjectCreate, ProjectUpdate
from app.storage.database import Base
from app.storage.models import Conversation, KnowledgeChunk, KnowledgeDocument, KnowledgeFolder, Project, User

TEST_EMBEDDING = [0.1] * 1024


class ProjectsApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db: Session = self.session_factory()
        self.user = User(username="project-user", password_hash="hash", is_active=True)
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_create_list_and_update_project(self):
        project = create_project(
            payload=ProjectCreate(name="  Client A  ", description="  launch  "),
            db=self.db,
            current_user=self.user,
        )

        self.assertEqual(project.name, "Client A")
        self.assertEqual(project.description, "launch")
        self.assertEqual([item.id for item in list_projects(db=self.db, current_user=self.user)], [project.id])

        updated = update_project(
            project_id=project.id,
            payload=ProjectUpdate(name="Client A Workspace", description="updated"),
            db=self.db,
            current_user=self.user,
        )

        self.assertEqual(updated.name, "Client A Workspace")
        self.assertEqual(updated.description, "updated")

    def test_delete_project_detaches_content_without_deleting_it(self):
        project = Project(user_id=self.user.id, name="Research")
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)

        conversation = Conversation(
            user_id=self.user.id,
            project_id=project.id,
            title="Project chat",
            model="openai:test",
        )
        document = KnowledgeDocument(
            user_id=self.user.id,
            project_id=project.id,
            title="notes.md",
            mime_type="text/markdown",
            extension=".md",
            size_bytes=12,
            relative_path=f"{self.user.id}/notes.md",
            sha1="abc",
            status="ready",
        )
        folder = KnowledgeFolder(user_id=self.user.id, project_id=project.id, name="notes")
        self.db.add_all([conversation, document, folder])
        self.db.flush()
        chunk = KnowledgeChunk(
            document_id=document.id,
            user_id=self.user.id,
            project_id=project.id,
            chunk_key="notes-0",
            chunk_index=0,
            path="notes.md",
            directory="",
            heading="Overview",
            content="project notes",
            token_count=3,
            tags_json="[]",
            embedding=TEST_EMBEDDING,
        )
        self.db.add(chunk)
        self.db.commit()

        delete_project(project_id=project.id, db=self.db, current_user=self.user)

        self.assertIsNone(self.db.get(Project, project.id))
        self.assertIsNone(self.db.scalar(select(Conversation.project_id).where(Conversation.id == conversation.id)))
        self.assertIsNone(self.db.scalar(select(KnowledgeDocument.project_id).where(KnowledgeDocument.id == document.id)))
        self.assertIsNone(self.db.scalar(select(KnowledgeFolder.project_id).where(KnowledgeFolder.id == folder.id)))
        self.assertIsNone(self.db.scalar(select(KnowledgeChunk.project_id).where(KnowledgeChunk.id == chunk.id)))


if __name__ == "__main__":
    unittest.main()
