import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import UploadFile
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.knowledge.service import KnowledgeService
from app.retrieval.rag.types import RagChunk, RetrievalCandidate
from app.storage.database import Base
from app.storage.models import KnowledgeChunk, KnowledgeDocument, KnowledgeFolder, User

TEST_EMBEDDING = [0.1] * 1024


class _FakeEmbedder:
    def __init__(self, settings, model_name):
        self.model_name = model_name

    async def embed_chunk_specs(self, chunk_specs):
        return (
            [
                RagChunk(
                    id=spec.id,
                    path=spec.path,
                    directory=spec.directory,
                    heading=spec.heading,
                    content=spec.content,
                    order=spec.order,
                    embedding=TEST_EMBEDDING,
                    tags=list(spec.tags),
                )
                for spec in chunk_specs
            ],
            [],
        )

    async def embed_query(self, query):
        return TEST_EMBEDDING


class _FakeReranker:
    def __init__(self, settings, rerank_window):
        self.rerank_window = rerank_window
        self.enabled = True
        self.disabled_reason = None

    async def rerank(self, query, candidates):
        return candidates


def make_settings(storage_root: str):
    return SimpleNamespace(
        knowledge_storage_root=storage_root,
        knowledge_max_file_size_bytes=2 * 1024 * 1024,
        knowledge_max_documents_per_user=100,
        knowledge_max_total_size_bytes=100 * 1024 * 1024,
        knowledge_top_k=4,
        knowledge_section_max_chars=1400,
        knowledge_candidate_limit=12,
        knowledge_rerank_window=12,
        knowledge_neighbor_window=1,
        knowledge_min_score=0.22,
        knowledge_embedding_model="qwen3-embedding:0.6b",
        knowledge_rerank_model="dengcao/Qwen3-Reranker-0.6B:Q8_0",
    )


class KnowledgeServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
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
        self.temp_dir.cleanup()

    async def test_reindex_document_replaces_existing_chunks_without_deleted_instance_error(self):
        user = User(username="alice", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        document = KnowledgeDocument(
            user_id=user.id,
            title="notes.md",
            mime_type="text/markdown",
            extension=".md",
            size_bytes=32,
            relative_path=f"{user.id}/1.md",
            sha1="abc123",
            status="ready",
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        self.db.add(
            KnowledgeChunk(
                document_id=document.id,
                user_id=user.id,
                chunk_key="legacy",
                chunk_index=0,
                path="notes.md",
                directory="",
                heading="Old",
                content="old content",
                token_count=2,
                tags_json="[]",
                embedding=TEST_EMBEDDING,
            )
        )
        self.db.commit()

        file_path = Path(self.temp_dir.name) / f"{user.id}" / "1.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("# Title\n\n## Section\n\nnew content", encoding="utf-8")

        settings = make_settings(self.temp_dir.name)
        with patch("app.knowledge.service.build_knowledge_embedder", return_value=_FakeEmbedder(settings, settings.knowledge_embedding_model)), patch(
            "app.knowledge.service.ModelReranker", _FakeReranker
        ):
            service = KnowledgeService(settings)
            indexed = await service.reindex_document(
                db=self.db,
                user_id=user.id,
                document_id=document.id,
            )

        self.assertIsNotNone(indexed)
        self.assertEqual(indexed.status, "ready")
        chunk_keys = list(
            self.db.scalars(
                select(KnowledgeChunk.chunk_key).where(KnowledgeChunk.document_id == document.id)
            ).all()
        )
        self.assertNotIn("legacy", chunk_keys)
        self.assertGreater(len(chunk_keys), 0)

    async def test_batch_upload_and_delete_documents(self):
        user = User(username="bob", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        settings = make_settings(self.temp_dir.name)
        with patch("app.knowledge.service.build_knowledge_embedder", return_value=_FakeEmbedder(settings, settings.knowledge_embedding_model)), patch(
            "app.knowledge.service.ModelReranker", _FakeReranker
        ):
            service = KnowledgeService(settings)
            self.assertEqual(service.create_folder(db=self.db, user_id=user.id, name="product"), "product")
            self.assertEqual(service.list_folders(db=self.db, user_id=user.id), ["product"])

            documents = await service.create_documents(
                db=self.db,
                user_id=user.id,
                folder="project-a",
                uploads=[
                    UploadFile(filename="a.md", file=BytesIO(b"# A\n\nhello"), headers=None),
                    UploadFile(filename="b.md", file=BytesIO(b"# B\n\nworld"), headers=None),
                ],
            )

            self.assertEqual(len(documents), 2)
            self.assertEqual(service.list_folders(db=self.db, user_id=user.id), ["product", "project-a"])
            self.assertEqual(
                list(self.db.scalars(select(KnowledgeDocument.title).order_by(KnowledgeDocument.id.asc())).all()),
                ["a.md", "b.md"],
            )
            self.assertEqual([document.path for document in documents], ["project-a/a.md", "project-a/b.md"])

            moved_documents = service.move_documents(
                db=self.db,
                user_id=user.id,
                document_ids=[documents[0].id, documents[1].id],
                folder="project-b/archive",
            )
            self.assertEqual([document.path for document in moved_documents], ["project-b/archive/a.md", "project-b/archive/b.md"])
            self.assertEqual(
                service.list_folders(db=self.db, user_id=user.id),
                ["product", "project-a", "project-b/archive"],
            )

            delete_folder_result = service.delete_folder(
                db=self.db,
                user_id=user.id,
                name="project-b/archive",
            )
            self.assertEqual(
                delete_folder_result,
                {"folder": "project-b/archive", "moved_document_count": 2},
            )
            self.assertEqual(
                [
                    document.path
                    for document in self.db.scalars(
                        select(KnowledgeDocument).order_by(KnowledgeDocument.id.asc())
                    ).all()
                ],
                ["a.md", "b.md"],
            )
            self.assertIsNone(
                self.db.scalar(
                    select(KnowledgeFolder).where(
                        KnowledgeFolder.user_id == user.id,
                        KnowledgeFolder.name == "project-b/archive",
                    )
                )
            )
            self.assertEqual(
                service.list_folders(db=self.db, user_id=user.id),
                ["product", "project-a"],
            )

            deleted_ids, deleted_paths = service.delete_documents(
                db=self.db,
                user_id=user.id,
                document_ids=[documents[0].id, documents[1].id],
            )

            self.assertEqual(deleted_ids, [documents[0].id, documents[1].id])
            self.assertEqual(len(deleted_paths), 2)
            self.assertEqual(self.db.scalar(select(func.count(KnowledgeDocument.id))), 0)
            self.assertEqual(
                service.list_folders(db=self.db, user_id=user.id),
                ["product", "project-a"],
            )

    async def test_retrieve_context_applies_query_filters_for_in_memory_rag(self):
        user = User(username="carol", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        agent_doc = KnowledgeDocument(
            user_id=user.id,
            title="agent-plan.md",
            mime_type="text/markdown",
            extension=".md",
            size_bytes=64,
            relative_path=f"{user.id}/agent-plan.md",
            sha1="agent-plan",
            status="ready",
        )
        daily_doc = KnowledgeDocument(
            user_id=user.id,
            title="daily-log.md",
            mime_type="text/markdown",
            extension=".md",
            size_bytes=64,
            relative_path=f"{user.id}/daily-log.md",
            sha1="daily-log",
            status="ready",
        )
        self.db.add_all([agent_doc, daily_doc])
        self.db.commit()
        self.db.refresh(agent_doc)
        self.db.refresh(daily_doc)

        self.db.add_all(
            [
                KnowledgeChunk(
                    document_id=agent_doc.id,
                    user_id=user.id,
                    chunk_key="agent-0",
                    chunk_index=0,
                    path="agent-plan.md",
                    directory="work",
                    heading="Plan",
                    content="KPI 改造方案需要拆成里程碑并推进执行。",
                    token_count=10,
                    tags_json='["agent"]',
                    embedding=TEST_EMBEDDING,
                ),
                KnowledgeChunk(
                    document_id=daily_doc.id,
                    user_id=user.id,
                    chunk_key="daily-0",
                    chunk_index=0,
                    path="daily-log.md",
                    directory="personal",
                    heading="Notes",
                    content="KPI 改造方案需要拆成里程碑并推进执行。",
                    token_count=10,
                    tags_json='["daily"]',
                    embedding=TEST_EMBEDDING,
                ),
            ]
        )
        self.db.commit()

        settings = make_settings(self.temp_dir.name)
        with patch("app.knowledge.service.build_knowledge_embedder", return_value=_FakeEmbedder(settings, settings.knowledge_embedding_model)), patch(
            "app.knowledge.service.ModelReranker", _FakeReranker
        ):
            service = KnowledgeService(settings)
            payload = await service.retrieve_context(
                db=self.db,
                user_id=user.id,
                query="tag:agent KPI 改造方案",
            )

        self.assertFalse(payload.should_refuse)
        self.assertEqual([entry.source.path for entry in payload.entries], ["agent-plan.md"])
        self.assertEqual([source.path for source in payload.sources], ["agent-plan.md"])

        with patch("app.knowledge.service.build_knowledge_embedder", return_value=_FakeEmbedder(settings, settings.knowledge_embedding_model)), patch(
            "app.knowledge.service.ModelReranker", _FakeReranker
        ):
            service = KnowledgeService(settings)
            scoped_payload = await service.retrieve_context(
                db=self.db,
                user_id=user.id,
                query="KPI 改造方案",
                folders=["personal"],
            )

        self.assertFalse(scoped_payload.should_refuse)
        self.assertEqual([entry.source.path for entry in scoped_payload.entries], ["daily-log.md"])

    async def test_retrieve_context_loads_postgres_neighbor_chunks_from_database_pool(self):
        user = User(username="dave", password_hash="hash", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        document = KnowledgeDocument(
            user_id=user.id,
            title="notes.md",
            mime_type="text/markdown",
            extension=".md",
            size_bytes=96,
            relative_path=f"{user.id}/notes.md",
            sha1="notes",
            status="ready",
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        self.db.add_all(
            [
                KnowledgeChunk(
                    document_id=document.id,
                    user_id=user.id,
                    chunk_key="notes-0",
                    chunk_index=0,
                    path="notes.md",
                    directory="work",
                    heading="Intro",
                    content="前置背景",
                    token_count=4,
                    tags_json='["debate"]',
                    embedding=TEST_EMBEDDING,
                ),
                KnowledgeChunk(
                    document_id=document.id,
                    user_id=user.id,
                    chunk_key="notes-1",
                    chunk_index=1,
                    path="notes.md",
                    directory="work",
                    heading="Core",
                    content="关键论点",
                    token_count=4,
                    tags_json='["debate"]',
                    embedding=TEST_EMBEDDING,
                ),
                KnowledgeChunk(
                    document_id=document.id,
                    user_id=user.id,
                    chunk_key="notes-2",
                    chunk_index=2,
                    path="notes.md",
                    directory="work",
                    heading="Summary",
                    content="总结结论",
                    token_count=4,
                    tags_json='["debate"]',
                    embedding=TEST_EMBEDDING,
                ),
            ]
        )
        self.db.commit()

        settings = make_settings(self.temp_dir.name)
        with patch("app.knowledge.service.build_knowledge_embedder", return_value=_FakeEmbedder(settings, settings.knowledge_embedding_model)), patch(
            "app.knowledge.service.ModelReranker", _FakeReranker
        ):
            service = KnowledgeService(settings)
            context_pool = [
                RagChunk(
                    id="notes-0",
                    path="notes.md",
                    directory="work",
                    heading="Intro",
                    content="前置背景",
                    order=0,
                    embedding=TEST_EMBEDDING,
                    tags=["debate"],
                ),
                RagChunk(
                    id="notes-1",
                    path="notes.md",
                    directory="work",
                    heading="Core",
                    content="关键论点",
                    order=1,
                    embedding=TEST_EMBEDDING,
                    tags=["debate"],
                ),
                RagChunk(
                    id="notes-2",
                    path="notes.md",
                    directory="work",
                    heading="Summary",
                    content="总结结论",
                    order=2,
                    embedding=TEST_EMBEDDING,
                    tags=["debate"],
                ),
            ]
            primary_candidate = RetrievalCandidate(
                chunk=context_pool[1],
                vector_score=0.9,
                keyword_score=0.7,
                hybrid_score=0.85,
                final_score=0.85,
            )

            original_dialect_name = self.db.bind.dialect.name
            self.db.bind.dialect.name = "postgresql"
            try:
                with patch.object(service, "_retrieve_postgres_candidates", return_value=[primary_candidate]), patch.object(
                    service,
                    "_load_postgres_context_chunk_pool",
                    return_value=context_pool,
                ) as load_context_pool:
                    payload = await service.retrieve_context(
                        db=self.db,
                        user_id=user.id,
                        query="关键论点",
                    )
            finally:
                self.db.bind.dialect.name = original_dialect_name

        self.assertFalse(payload.should_refuse)
        self.assertEqual([entry.source.heading for entry in payload.entries], ["Intro", "Core", "Summary"])
        self.assertEqual(payload.debug["knowledge_context_chunk_count"], 3)
        load_context_pool.assert_called_once()


if __name__ == "__main__":
    unittest.main()
